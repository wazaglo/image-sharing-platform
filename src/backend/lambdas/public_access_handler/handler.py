import json
import os
import hashlib
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

FOLDERS_TABLE = os.environ.get('FOLDERS_TABLE', 'Folders')
FILES_TABLE = os.environ.get('FILES_TABLE', 'Files')
SHARES_TABLE = os.environ.get('SHARES_TABLE', 'Shares')
BUCKET = os.environ.get('BUCKET_NAME', '')
USERS_PREFIX = os.environ.get('USERS_PREFIX', 'users/')
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
            'Access-Control-Allow-Origin': f'https://{CLOUDFRONT_DOMAIN}',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization'
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }

def parse_body(event: Dict) -> Dict:
    try:
        return json.loads(event.get('body', '{}'))
    except (json.JSONDecodeError, TypeError):
        return {}

def get_path_parameter(event: Dict, param: str) -> str:
    try:
        return event['pathParameters'][param]
    except (KeyError, TypeError):
        return ''

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
        except Exception:
            pass
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

    return {**file_item, 'presignedUrl': presigned_url, 'thumbnailUrl': thumbnail_url}


def lambda_handler(event: Dict, context) -> Dict:
    logger.info(f'Event: {json.dumps(event)}')
    try:
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
        token = get_path_parameter(event, 'token')

        if not token:
            return response(400, {'error': 'Missing share token'})

        shares_table = dynamodb.Table(SHARES_TABLE)
        share_resp = shares_table.scan(
            FilterExpression=Attr('shareToken').eq(token)
        )
        shares = share_resp.get('Items', [])
        if not shares:
            return response(404, {'error': 'Share not found'})

        share = shares[0]
        owner = share.get('PK', '')
        folder_id = share.get('folderId', '')

        expiry = share.get('expiry', '')
        if expiry:
            try:
                expiry_dt = datetime.fromisoformat(expiry)
                if expiry_dt < datetime.now(timezone.utc):
                    return response(410, {'error': 'Share link has expired'})
            except (ValueError, TypeError):
                pass

        pin_hash = share.get('pinHash', '')

        if http_method == 'GET' and 'verify' not in path:
            if pin_hash:
                return response(200, {
                    'success': True,
                    'requiresPin': True,
                    'shareToken': token,
                    'folderName': share.get('folderName', 'Shared Folder'),
                })

            return handle_get_folder(share, owner, folder_id)

        if http_method == 'POST' and path.endswith('/verify'):
            body = parse_body(event)
            provided_pin = body.get('pin', '')
            if not provided_pin:
                return response(400, {'error': 'PIN is required'})
            provided_hash = hashlib.sha256(provided_pin.encode()).hexdigest()
            if provided_hash != pin_hash:
                return response(403, {'error': 'Invalid PIN'})
            return handle_get_folder(share, owner, folder_id)

        if http_method == 'POST':
            permission = share.get('permission', 'view')
            if permission != 'edit':
                return response(403, {'error': 'This share does not allow uploads'})

            body = parse_body(event)
            file_name = body.get('fileName', '')
            content_type = body.get('contentType', 'application/octet-stream')
            size = body.get('size', 0)

            if not file_name:
                return response(400, {'error': 'fileName is required'})

            import uuid
            file_id = str(uuid.uuid4()).replace('-', '')[:20]
            s3_key = f'{USERS_PREFIX}{owner}/{folder_id}/{file_id}_{file_name}'

            try:
                presigned_url = s3.generate_presigned_url(
                    'put_object',
                    Params={'Bucket': BUCKET, 'Key': s3_key, 'ContentType': content_type},
                    ExpiresIn=3600
                )
            except Exception as e:
                logger.error(f'Failed to generate presigned URL: {e}')
                return response(500, {'error': 'Failed to generate upload URL'})

            files_table = dynamodb.Table(FILES_TABLE)
            now = datetime.now(timezone.utc).isoformat()
            item = {
                'PK': owner,
                'SK': f'FILE#{file_id}',
                'fileId': file_id,
                'fileName': file_name,
                'contentType': content_type,
                'size': size,
                'folderId': folder_id,
                'owner': owner,
                'ownerEmail': share.get('ownerEmail', ''),
                's3Key': s3_key,
                'isDeleted': False,
                'deletedAt': '',
                'createdAt': now,
                'updatedAt': now,
            }

            try:
                files_table.put_item(Item=item)
                return response(200, {'success': True, 'file': item, 'uploadUrl': presigned_url})
            except Exception as e:
                logger.error(f'Error saving file record: {e}')
                return response(500, {'error': 'Failed to save file record'})

        if http_method == 'OPTIONS':
            return response(200, {'success': True})

        return response(405, {'error': 'Method not allowed'})

    except Exception as e:
        logger.error(f'Unhandled error: {str(e)}', exc_info=True)
        return response(500, {'error': 'Internal server error'})


def handle_get_folder(share: Dict, owner: str, folder_id: str) -> Dict:
    folders_table = dynamodb.Table(FOLDERS_TABLE)
    files_table = dynamodb.Table(FILES_TABLE)

    try:
        folder_resp = folders_table.get_item(Key={'PK': owner, 'SK': f'FOLDER#{folder_id}'})
        folder = folder_resp.get('Item', {})

        subfolder_resp = folders_table.query(
            KeyConditionExpression=Key('PK').eq(owner) & Key('SK').begins_with('FOLDER#'),
            FilterExpression=Attr('parentId').eq(folder_id)
        )
        subfolders = subfolder_resp.get('Items', [])

        files_resp = files_table.query(
            KeyConditionExpression=Key('PK').eq(owner) & Key('SK').begins_with('FILE#'),
            FilterExpression=Attr('folderId').eq(folder_id) & Attr('isDeleted').eq(False)
        )
        files = files_resp.get('Items', [])
        enriched_files = [enrich_file(f) for f in files]

        return response(200, {
            'success': True,
            'folder': folder,
            'folderName': share.get('folderName', folder.get('name', 'Shared Folder')),
            'permission': share.get('permission', 'view'),
            'subfolders': subfolders,
            'files': enriched_files,
        })
    except Exception as e:
        logger.error(f'Error fetching shared folder contents: {e}')
        return response(500, {'error': 'Failed to fetch folder contents'})
