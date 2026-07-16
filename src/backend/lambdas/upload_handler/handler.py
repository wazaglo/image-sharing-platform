import json
import os
import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

BUCKET = os.environ.get('BUCKET_NAME', '')
FOLDERS_TABLE = os.environ.get('FOLDERS_TABLE', 'Folders')
FILES_TABLE = os.environ.get('FILES_TABLE', 'Files')
USERS_PREFIX = os.environ.get('USERS_PREFIX', 'users/')
TRASH_PREFIX = 'trash/'
THUMBNAIL_PREFIX = os.environ.get('THUMBNAIL_PREFIX', 'thumbnails/')
CLOUDFRONT_DOMAIN = os.environ.get('CLOUDFRONT_DOMAIN', '')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)

def response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization'
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }

def get_user_from_event(event: Dict) -> tuple:
    try:
        claims = event['requestContext']['authorizer']['claims']
        return claims['sub'], claims.get('email', '')
    except (KeyError, TypeError):
        return None, None

def parse_body(event: Dict) -> Dict:
    try:
        return json.loads(event.get('body', '{}'))
    except (json.JSONDecodeError, TypeError):
        return {}

def generate_file_id() -> str:
    return str(uuid.uuid4()).replace('-', '')[:20]

def enrich_file(file_item: Dict) -> Dict:
    file_key = file_item.get('s3Key', '')
    presigned_url = ''
    thumbnail_url = ''

    if file_key:
        try:
            presigned_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': BUCKET, 'Key': file_key},
                ExpiresIn=3600
            )
        except Exception as e:
            logger.warning(f'Failed to generate presigned URL for {file_key}: {e}')

        try:
            thumb_key = file_key.replace(USERS_PREFIX, THUMBNAIL_PREFIX, 1)
            s3.head_object(Bucket=BUCKET, Key=thumb_key)
            if CLOUDFRONT_DOMAIN:
                thumbnail_url = f'https://{CLOUDFRONT_DOMAIN}/{thumb_key}'
            else:
                thumbnail_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': BUCKET, 'Key': thumb_key},
                    ExpiresIn=3600
                )
        except Exception:
            pass

    return {
        **file_item,
        'presignedUrl': presigned_url,
        'thumbnailUrl': thumbnail_url,
    }


def lambda_handler(event: Dict, context) -> Dict:
    logger.info(f'Event: {json.dumps(event)}')
    try:
        sub, email = get_user_from_event(event)
        if not sub:
            return response(401, {'error': 'Unauthorized'})

        body = parse_body(event)
        action = body.get('action', '')

        handlers = {
            'upload': handle_upload,
            'list': handle_list,
            'search': handle_search,
            'delete': handle_delete,
            'rename': handle_rename,
            'move': handle_move,
            'trash': handle_trash,
            'restore': handle_restore,
            'emptyTrash': handle_empty_trash,
        }

        handler = handlers.get(action)
        if not handler:
            return response(400, {'error': f'Unknown action: {action}'})

        return handler(body, sub, email)

    except Exception as e:
        logger.error(f'Unhandled error: {str(e)}', exc_info=True)
        return response(500, {'error': 'Internal server error'})


def handle_upload(body: Dict, sub: str, email: str) -> Dict:
    files_table = dynamodb.Table(FILES_TABLE)
    file_name = body.get('fileName', '')
    content_type = body.get('contentType', 'application/octet-stream')
    size = body.get('size', 0)
    folder_id = body.get('folderId', 'root')

    if not file_name:
        return response(400, {'error': 'fileName is required'})

    file_id = generate_file_id()
    s3_key = f'{USERS_PREFIX}{sub}/{folder_id}/{file_id}_{file_name}'

    try:
        presigned_upload_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET,
                'Key': s3_key,
                'ContentType': content_type,
            },
            ExpiresIn=3600
        )
    except Exception as e:
        logger.error(f'Failed to generate presigned upload URL: {e}')
        return response(500, {'error': 'Failed to generate upload URL'})

    now = datetime.now(timezone.utc).isoformat()
    item = {
        'PK': sub,
        'SK': f'FILE#{file_id}',
        'fileId': file_id,
        'fileName': file_name,
        'contentType': content_type,
        'size': size,
        'folderId': folder_id,
        'owner': sub,
        'ownerEmail': email,
        's3Key': s3_key,
        'isDeleted': False,
        'deletedAt': '',
        'createdAt': now,
        'updatedAt': now,
    }

    try:
        files_table.put_item(Item=item)
        logger.info(f'File record created: {file_id} by {email}')
        return response(200, {
            'success': True,
            'file': item,
            'uploadUrl': presigned_upload_url,
            's3Key': s3_key,
        })
    except Exception as e:
        logger.error(f'Error creating file record: {e}')
        return response(500, {'error': 'Failed to create file record'})


def handle_list(body: Dict, sub: str, email: str) -> Dict:
    files_table = dynamodb.Table(FILES_TABLE)
    folder_id = body.get('folderId', 'root')
    include_deleted = body.get('includeDeleted', False)

    try:
        if include_deleted:
            resp = files_table.query(
                KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FILE#'),
                FilterExpression=Attr('folderId').eq(folder_id)
            )
        else:
            resp = files_table.query(
                KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FILE#'),
                FilterExpression=Attr('folderId').eq(folder_id) & Attr('isDeleted').eq(False)
            )

        files = resp.get('Items', [])
        enriched = [enrich_file(f) for f in files]
        return response(200, {'success': True, 'files': enriched})
    except Exception as e:
        logger.error(f'Error listing files: {e}')
        return response(500, {'error': 'Failed to list files'})


def handle_search(body: Dict, sub: str, email: str) -> Dict:
    files_table = dynamodb.Table(FILES_TABLE)
    query_text = body.get('query', '').lower().strip()

    if not query_text:
        return response(400, {'error': 'query is required'})

    try:
        resp = files_table.query(
            KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FILE#'),
            FilterExpression=Attr('isDeleted').eq(False)
        )
        all_files = resp.get('Items', [])
        matched = [f for f in all_files if query_text in f.get('fileName', '').lower()]
        enriched = [enrich_file(f) for f in matched]
        return response(200, {'success': True, 'files': enriched})
    except Exception as e:
        logger.error(f'Error searching files: {e}')
        return response(500, {'error': 'Failed to search files'})


def handle_delete(body: Dict, sub: str, email: str) -> Dict:
    files_table = dynamodb.Table(FILES_TABLE)
    file_id = body.get('fileId', '')

    if not file_id:
        return response(400, {'error': 'fileId is required'})

    try:
        resp = files_table.get_item(Key={'PK': sub, 'SK': f'FILE#{file_id}'})
        file_item = resp.get('Item')
        if not file_item:
            return response(404, {'error': 'File not found'})

        s3_key = file_item.get('s3Key', '')
        if s3_key:
            try:
                s3.delete_object(Bucket=BUCKET, Key=s3_key)
                logger.info(f'S3 object deleted: {s3_key}')
            except Exception as e:
                logger.error(f'Failed to delete S3 object: {e}')

            try:
                thumb_key = s3_key.replace(USERS_PREFIX, THUMBNAIL_PREFIX, 1)
                s3.delete_object(Bucket=BUCKET, Key=thumb_key)
            except Exception:
                pass

        files_table.delete_item(Key={'PK': sub, 'SK': f'FILE#{file_id}'})
        logger.info(f'File permanently deleted: {file_id} by {email}')
        return response(200, {'success': True})
    except Exception as e:
        logger.error(f'Error deleting file: {e}')
        return response(500, {'error': 'Failed to delete file'})


def handle_rename(body: Dict, sub: str, email: str) -> Dict:
    files_table = dynamodb.Table(FILES_TABLE)
    file_id = body.get('fileId', '')
    new_name = body.get('fileName', '').strip()

    if not file_id or not new_name:
        return response(400, {'error': 'fileId and fileName are required'})

    try:
        now = datetime.now(timezone.utc).isoformat()
        files_table.update_item(
            Key={'PK': sub, 'SK': f'FILE#{file_id}'},
            UpdateExpression='SET fileName = :name, updatedAt = :now',
            ExpressionAttributeValues={':name': new_name, ':now': now},
            ConditionExpression='attribute_exists(PK)'
        )
        logger.info(f'File renamed: {file_id} to {new_name} by {email}')
        return response(200, {'success': True})
    except Exception as e:
        logger.error(f'Error renaming file: {e}')
        return response(500, {'error': 'Failed to rename file'})


def handle_move(body: Dict, sub: str, email: str) -> Dict:
    files_table = dynamodb.Table(FILES_TABLE)
    file_id = body.get('fileId', '')
    target_folder_id = body.get('targetFolderId', '')

    if not file_id or not target_folder_id:
        return response(400, {'error': 'fileId and targetFolderId are required'})

    try:
        resp = files_table.get_item(Key={'PK': sub, 'SK': f'FILE#{file_id}'})
        file_item = resp.get('Item')
        if not file_item:
            return response(404, {'error': 'File not found'})

        old_key = file_item.get('s3Key', '')
        file_name_part = old_key.split('_', 1)[1] if '_' in old_key else file_item.get('fileName', '')
        new_s3_key = f'{USERS_PREFIX}{sub}/{target_folder_id}/{file_id}_{file_name_part}'

        if old_key:
            try:
                s3.copy_object(
                    Bucket=BUCKET,
                    CopySource={'Bucket': BUCKET, 'Key': old_key},
                    Key=new_s3_key
                )
                s3.delete_object(Bucket=BUCKET, Key=old_key)
                logger.info(f'S3 object moved: {old_key} -> {new_s3_key}')
            except Exception as e:
                logger.error(f'Failed to move S3 object: {e}')

        now = datetime.now(timezone.utc).isoformat()
        files_table.update_item(
            Key={'PK': sub, 'SK': f'FILE#{file_id}'},
            UpdateExpression='SET folderId = :fid, s3Key = :key, updatedAt = :now',
            ExpressionAttributeValues={
                ':fid': target_folder_id,
                ':key': new_s3_key,
                ':now': now
            },
            ConditionExpression='attribute_exists(PK)'
        )
        logger.info(f'File moved: {file_id} by {email}')
        return response(200, {'success': True})
    except Exception as e:
        logger.error(f'Error moving file: {e}')
        return response(500, {'error': 'Failed to move file'})


def handle_trash(body: Dict, sub: str, email: str) -> Dict:
    files_table = dynamodb.Table(FILES_TABLE)
    file_id = body.get('fileId', '')

    if not file_id:
        return response(400, {'error': 'fileId is required'})

    try:
        resp = files_table.get_item(Key={'PK': sub, 'SK': f'FILE#{file_id}'})
        file_item = resp.get('Item')
        if not file_item:
            return response(404, {'error': 'File not found'})

        old_key = file_item.get('s3Key', '')
        if old_key:
            trash_key = f'{USERS_PREFIX}{sub}/{TRASH_PREFIX}{file_id}_{file_item.get("fileName", "")}'
            try:
                s3.copy_object(
                    Bucket=BUCKET,
                    CopySource={'Bucket': BUCKET, 'Key': old_key},
                    Key=trash_key
                )
                s3.delete_object(Bucket=BUCKET, Key=old_key)
                logger.info(f'File moved to trash: {old_key} -> {trash_key}')
            except Exception as e:
                logger.error(f'Failed to move to trash: {e}')

            try:
                thumb_key = old_key.replace(USERS_PREFIX, THUMBNAIL_PREFIX, 1)
                thumb_trash_key = trash_key.replace(USERS_PREFIX, THUMBNAIL_PREFIX, 1)
                s3.copy_object(
                    Bucket=BUCKET,
                    CopySource={'Bucket': BUCKET, 'Key': thumb_key},
                    Key=thumb_trash_key
                )
                s3.delete_object(Bucket=BUCKET, Key=thumb_key)
            except Exception:
                pass

        now = datetime.now(timezone.utc).isoformat()
        files_table.update_item(
            Key={'PK': sub, 'SK': f'FILE#{file_id}'},
            UpdateExpression='SET isDeleted = :del, deletedAt = :now, s3Key = :newKey',
            ExpressionAttributeValues={
                ':del': True,
                ':now': now,
                ':newKey': f'{USERS_PREFIX}{sub}/{TRASH_PREFIX}{file_id}_{file_item.get("fileName", "")}'
            },
            ConditionExpression='attribute_exists(PK)'
        )
        logger.info(f'File trashed: {file_id} by {email}')
        return response(200, {'success': True})
    except Exception as e:
        logger.error(f'Error trashing file: {e}')
        return response(500, {'error': 'Failed to trash file'})


def handle_restore(body: Dict, sub: str, email: str) -> Dict:
    files_table = dynamodb.Table(FILES_TABLE)
    file_id = body.get('fileId', '')

    if not file_id:
        return response(400, {'error': 'fileId is required'})

    try:
        resp = files_table.get_item(Key={'PK': sub, 'SK': f'FILE#{file_id}'})
        file_item = resp.get('Item')
        if not file_item:
            return response(404, {'error': 'File not found'})

        trash_key = file_item.get('s3Key', '')
        folder_id = file_item.get('folderId', 'root')
        original_key = f'{USERS_PREFIX}{sub}/{folder_id}/{file_id}_{file_item.get("fileName", "")}'

        if trash_key:
            try:
                s3.copy_object(
                    Bucket=BUCKET,
                    CopySource={'Bucket': BUCKET, 'Key': trash_key},
                    Key=original_key
                )
                s3.delete_object(Bucket=BUCKET, Key=trash_key)
                logger.info(f'File restored from trash: {trash_key} -> {original_key}')
            except Exception as e:
                logger.error(f'Failed to restore from trash: {e}')

            try:
                thumb_trash_key = trash_key.replace(USERS_PREFIX, THUMBNAIL_PREFIX, 1)
                thumb_original_key = original_key.replace(USERS_PREFIX, THUMBNAIL_PREFIX, 1)
                s3.copy_object(
                    Bucket=BUCKET,
                    CopySource={'Bucket': BUCKET, 'Key': thumb_trash_key},
                    Key=thumb_original_key
                )
                s3.delete_object(Bucket=BUCKET, Key=thumb_trash_key)
            except Exception:
                pass

        now = datetime.now(timezone.utc).isoformat()
        files_table.update_item(
            Key={'PK': sub, 'SK': f'FILE#{file_id}'},
            UpdateExpression='SET isDeleted = :del, deletedAt = :empty, s3Key = :key, updatedAt = :now',
            ExpressionAttributeValues={
                ':del': False,
                ':empty': '',
                ':key': original_key,
                ':now': now
            },
            ConditionExpression='attribute_exists(PK)'
        )
        logger.info(f'File restored: {file_id} by {email}')
        return response(200, {'success': True})
    except Exception as e:
        logger.error(f'Error restoring file: {e}')
        return response(500, {'error': 'Failed to restore file'})


def handle_empty_trash(body: Dict, sub: str, email: str) -> Dict:
    files_table = dynamodb.Table(FILES_TABLE)

    try:
        resp = files_table.query(
            KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FILE#'),
            FilterExpression=Attr('isDeleted').eq(True)
        )
        trashed_files = resp.get('Items', [])

        for f in trashed_files:
            s3_key = f.get('s3Key', '')
            if s3_key:
                try:
                    s3.delete_object(Bucket=BUCKET, Key=s3_key)
                except Exception:
                    pass
                try:
                    thumb_key = s3_key.replace(USERS_PREFIX, THUMBNAIL_PREFIX, 1)
                    s3.delete_object(Bucket=BUCKET, Key=thumb_key)
                except Exception:
                    pass
            files_table.delete_item(Key={'PK': sub, 'SK': f'FILE#{f["fileId"]}'})

        logger.info(f'Trash emptied by {email}: {len(trashed_files)} files')
        return response(200, {'success': True, 'deletedCount': len(trashed_files)})
    except Exception as e:
        logger.error(f'Error emptying trash: {e}')
        return response(500, {'error': 'Failed to empty trash'})
