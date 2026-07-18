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
cognito = boto3.client('cognito-idp')

BUCKET = os.environ.get('BUCKET_NAME', '')
FOLDERS_TABLE = os.environ.get('FOLDERS_TABLE', 'Folders')
FILES_TABLE = os.environ.get('FILES_TABLE', 'Files')
SHARES_TABLE = os.environ.get('SHARES_TABLE', 'Shares')
USERS_PREFIX = os.environ.get('USERS_PREFIX', 'users/')
ADMIN_EMAILS = os.environ.get('ADMIN_EMAILS', '').split(',')
USER_POOL_ID = os.environ.get('USER_POOL_ID', '')
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

def is_admin(email: str) -> bool:
    return email in ADMIN_EMAILS

def generate_folder_id() -> str:
    return str(uuid.uuid4())

def lambda_handler(event: Dict, context) -> Dict:
    logger.info(f'Event: {json.dumps(event)}')
    try:
        sub, email = get_user_from_event(event)
        if not sub:
            return response(401, {'error': 'Unauthorized'})

        body = parse_body(event)
        action = body.get('action', '')

        handlers = {
            'create': handle_create,
            'list': handle_list,
            'delete': handle_delete,
            'rename': handle_rename,
            'stats': handle_stats,
            'deleteAccount': handle_delete_account,
            'adminListUsers': handle_admin_list_users,
            'adminDeleteUser': handle_admin_delete_user,
            'sharedWithMe': handle_shared_with_me,
        }

        handler = handlers.get(action)
        if not handler:
            return response(400, {'error': f'Unknown action: {action}'})

        return handler(body, sub, email)

    except Exception as e:
        logger.error(f'Unhandled error: {str(e)}', exc_info=True)
        return response(500, {'error': 'Internal server error'})


def handle_create(body: Dict, sub: str, email: str) -> Dict:
    folders_table = dynamodb.Table(FOLDERS_TABLE)
    name = body.get('name', '').strip()
    parent_id = body.get('parentId', 'root')

    if not name:
        return response(400, {'error': 'Folder name is required'})

    folder_id = generate_folder_id()
    now = datetime.now(timezone.utc).isoformat()

    item = {
        'PK': sub,
        'SK': f'FOLDER#{folder_id}',
        'folderId': folder_id,
        'name': name,
        'parentId': parent_id,
        'owner': sub,
        'ownerEmail': email,
        'createdAt': now,
        'updatedAt': now,
        'isShared': False,
        'shareToken': '',
        'sharePin': '',
        'shareExpiry': '',
        'sharePermission': '',
        'sharedWithEmails': [],
    }

    try:
        folders_table.put_item(Item=item)
        logger.info(f'Folder created: {folder_id} by {email}')
        return response(200, {'success': True, 'folder': item})
    except Exception as e:
        logger.error(f'Error creating folder: {str(e)}')
        return response(500, {'error': 'Failed to create folder'})


def handle_list(body: Dict, sub: str, email: str) -> Dict:
    folders_table = dynamodb.Table(FOLDERS_TABLE)
    parent_id = body.get('parentId', 'root')

    try:
        resp = folders_table.query(
            KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#'),
            FilterExpression=Attr('parentId').eq(parent_id)
        )
        folders = resp.get('Items', [])
        for f in folders:
            if 'sharedWithEmails' in f and isinstance(f['sharedWithEmails'], list):
                f['sharedWithEmails'] = [e for e in f['sharedWithEmails'] if e]
        return response(200, {'success': True, 'folders': folders})
    except Exception as e:
        logger.error(f'Error listing folders: {str(e)}')
        return response(500, {'error': 'Failed to list folders'})


def handle_delete(body: Dict, sub: str, email: str) -> Dict:
    folders_table = dynamodb.Table(FOLDERS_TABLE)
    files_table = dynamodb.Table(FILES_TABLE)
    folder_id = body.get('folderId', '')
    recursive = body.get('recursive', True)

    if not folder_id:
        return response(400, {'error': 'folderId is required'})

    try:
        if recursive:
            delete_folder_recursive(folders_table, files_table, sub, folder_id)

        folders_table.delete_item(Key={'PK': sub, 'SK': f'FOLDER#{folder_id}'})
        logger.info(f'Folder deleted: {folder_id} by {email}')
        return response(200, {'success': True})
    except Exception as e:
        logger.error(f'Error deleting folder: {str(e)}')
        return response(500, {'error': 'Failed to delete folder'})


def delete_folder_recursive(folders_table, files_table, sub: str, folder_id: str):
    child_folders = folders_table.query(
        KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#'),
        FilterExpression=Attr('parentId').eq(folder_id)
    ).get('Items', [])

    for cf in child_folders:
        delete_folder_recursive(folders_table, files_table, sub, cf['folderId'])
        folders_table.delete_item(Key={'PK': sub, 'SK': f'FOLDER#{cf["folderId"]}'})

    child_files = files_table.query(
        KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FILE#'),
        FilterExpression=Attr('folderId').eq(folder_id)
    ).get('Items', [])

    for cf in child_files:
        try:
            file_key = cf.get('s3Key', '')
            if file_key:
                s3.delete_object(Bucket=BUCKET, Key=file_key)
                thumb_key = file_key.replace(USERS_PREFIX, 'thumbnails/', 1) if USERS_PREFIX else f'thumbnails/{file_key}'
                try:
                    s3.delete_object(Bucket=BUCKET, Key=thumb_key)
                except Exception:
                    pass
        except Exception:
            pass
        files_table.delete_item(Key={'PK': sub, 'SK': f'FILE#{cf["fileId"]}'})


def handle_rename(body: Dict, sub: str, email: str) -> Dict:
    folders_table = dynamodb.Table(FOLDERS_TABLE)
    folder_id = body.get('folderId', '')
    new_name = body.get('name', '').strip()

    if not folder_id or not new_name:
        return response(400, {'error': 'folderId and name are required'})

    try:
        now = datetime.now(timezone.utc).isoformat()
        folders_table.update_item(
            Key={'PK': sub, 'SK': f'FOLDER#{folder_id}'},
            UpdateExpression='SET #name = :name, updatedAt = :now',
            ExpressionAttributeNames={'#name': 'name'},
            ExpressionAttributeValues={':name': new_name, ':now': now},
            ConditionExpression='attribute_exists(PK)'
        )
        logger.info(f'Folder renamed: {folder_id} to {new_name} by {email}')
        return response(200, {'success': True})
    except Exception as e:
        logger.error(f'Error renaming folder: {str(e)}')
        return response(500, {'error': 'Failed to rename folder'})


def handle_stats(body: Dict, sub: str, email: str) -> Dict:
    folders_table = dynamodb.Table(FOLDERS_TABLE)
    files_table = dynamodb.Table(FILES_TABLE)

    try:
        folder_resp = folders_table.query(
            KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#')
        )
        total_folders = len(folder_resp.get('Items', []))

        file_resp = files_table.query(
            KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FILE#')
        )
        files = file_resp.get('Items', [])
        total_files = len(files)
        total_size = sum(int(f.get('size', 0)) for f in files)
        active_files = sum(1 for f in files if not f.get('isDeleted', False))
        trashed_files = total_files - active_files

        return response(200, {
            'success': True,
            'stats': {
                'totalFolders': total_folders,
                'totalFiles': total_files,
                'totalSize': total_size,
                'activeFiles': active_files,
                'trashedFiles': trashed_files,
            }
        })
    except Exception as e:
        logger.error(f'Error getting stats: {str(e)}')
        return response(500, {'error': 'Failed to get stats'})


def handle_delete_account(body: Dict, sub: str, email: str) -> Dict:
    folders_table = dynamodb.Table(FOLDERS_TABLE)
    files_table = dynamodb.Table(FILES_TABLE)
    shares_table = dynamodb.Table(SHARES_TABLE)

    try:
        folder_resp = folders_table.query(
            KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#')
        )
        for f in folder_resp.get('Items', []):
            delete_folder_recursive(folders_table, files_table, sub, f['folderId'])
            folders_table.delete_item(Key={'PK': sub, 'SK': f'FOLDER#{f["folderId"]}'})

        file_resp = files_table.query(
            KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FILE#')
        )
        for f in file_resp.get('Items', []):
            file_key = f.get('s3Key', '')
            if file_key:
                try:
                    s3.delete_object(Bucket=BUCKET, Key=file_key)
                except Exception:
                    pass
            files_table.delete_item(Key={'PK': sub, 'SK': f'FILE#{f["fileId"]}'})

        share_resp = shares_table.query(
            KeyConditionExpression=Key('PK').eq(sub)
        )
        for s in share_resp.get('Items', []):
            shares_table.delete_item(Key={'PK': sub, 'SK': s['SK']})

        try:
            cognito.admin_delete_user(
                UserPoolId=USER_POOL_ID,
                Username=sub
            )
            logger.info(f'Cognito user deleted: {sub}')
        except Exception as e:
            logger.error(f'Error deleting Cognito user: {str(e)}')

        logger.info(f'Account deleted: {email}')
        return response(200, {'success': True})
    except Exception as e:
        logger.error(f'Error deleting account: {str(e)}')
        return response(500, {'error': 'Failed to delete account'})


def handle_admin_list_users(body: Dict, sub: str, email: str) -> Dict:
    if not is_admin(email):
        return response(403, {'error': 'Forbidden'})

    try:
        users = []
        pagination_token = None
        while True:
            kwargs = {'UserPoolId': USER_POOL_ID, 'Limit': 60}
            if pagination_token:
                kwargs['PaginationToken'] = pagination_token
            resp = cognito.list_users(**kwargs)
            for u in resp.get('Users', []):
                attrs = {a['Name']: a['Value'] for a in u.get('Attributes', [])}
                users.append({
                    'sub': attrs.get('sub', ''),
                    'email': attrs.get('email', ''),
                    'status': u.get('UserStatus', ''),
                    'enabled': u.get('Enabled', True),
                    'createdAt': u.get('UserCreateDate', '').isoformat() if u.get('UserCreateDate') else '',
                })
            pagination_token = resp.get('PaginationToken')
            if not pagination_token:
                break

        return response(200, {'success': True, 'users': users})
    except Exception as e:
        logger.error(f'Error listing users: {str(e)}')
        return response(500, {'error': 'Failed to list users'})


def handle_admin_delete_user(body: Dict, sub: str, email: str) -> Dict:
    if not is_admin(email):
        return response(403, {'error': 'Forbidden'})

    target_sub = body.get('targetSub', '')
    if not target_sub:
        return response(400, {'error': 'targetSub is required'})

    try:
        cognito.admin_delete_user(
            UserPoolId=USER_POOL_ID,
            Username=target_sub
        )
        logger.info(f'Admin {email} deleted user: {target_sub}')
        return response(200, {'success': True})
    except Exception as e:
        logger.error(f'Error deleting user: {str(e)}')
        return response(500, {'error': 'Failed to delete user'})


def handle_shared_with_me(body: Dict, sub: str, email: str) -> Dict:
    shares_table = dynamodb.Table(SHARES_TABLE)
    folders_table = dynamodb.Table(FOLDERS_TABLE)
    files_table = dynamodb.Table(FILES_TABLE)

    try:
        share_resp = shares_table.scan(
            FilterExpression=Attr('sharedWithEmails').contains(email)
        )
        shares = share_resp.get('Items', [])

        result = []
        for share in shares:
            owner = share.get('PK', '')
            folder_id = share.get('folderId', '')
            folder_resp = folders_table.get_item(
                Key={'PK': owner, 'SK': f'FOLDER#{folder_id}'}
            )
            folder = folder_resp.get('Item', {})
            if not folder:
                continue

            files_resp = files_table.query(
                KeyConditionExpression=Key('PK').eq(owner) & Key('SK').begins_with('FILE#'),
                FilterExpression=Attr('folderId').eq(folder_id) & Attr('isDeleted').eq(False)
            )
            files = files_resp.get('Items', [])

            enriched_files = []
            for f in files:
                file_key = f.get('s3Key', '')
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
                        thumb_key = file_key.replace('users/', 'thumbnails/', 1)
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
                        thumbnail_url = ''
                enriched_files.append({
                    **f,
                    'presignedUrl': presigned_url,
                    'thumbnailUrl': thumbnail_url,
                })

            result.append({
                'share': share,
                'folder': folder,
                'files': enriched_files,
                'ownerEmail': folder.get('ownerEmail', ''),
            })

        return response(200, {'success': True, 'sharedItems': result})
    except Exception as e:
        logger.error(f'Error getting shared items: {str(e)}')
        return response(500, {'error': 'Failed to get shared items'})
