import json
import os
import base64
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

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
USERS_PREFIX = os.environ.get('USERS_PREFIX', 'users/')
CLOUDFRONT_DOMAIN = os.environ.get('CLOUDFRONT_DOMAIN', '')
USER_POOL_ID = os.environ.get('USER_POOL_ID', '')
WEB_CLIENT_ID = os.environ.get('WEB_CLIENT_ID', '')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)

def response(status_code: int, body: Any = None) -> Dict[str, Any]:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS,MKCOL,MOVE,PROPFIND',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        },
        'body': json.dumps(body, cls=DecimalEncoder) if body is not None else ''
    }


def get_basic_auth_credentials(event: Dict) -> Optional[tuple]:
    try:
        auth_header = event['headers'].get('Authorization', '')
        if not auth_header:
            auth_header = event['headers'].get('authorization', '')
        if not auth_header:
            return None
        if not auth_header.startswith('Basic '):
            return None
        encoded = auth_header.split(' ', 1)[1]
        decoded = base64.b64decode(encoded).decode('utf-8')
        username, password = decoded.split(':', 1)
        return username, password
    except (KeyError, ValueError, IndexError, TypeError):
        return None


def authenticate(event: Dict) -> Optional[Dict]:
    creds = get_basic_auth_credentials(event)
    if not creds:
        return None

    username, password = creds

    try:
        resp = cognito.admin_initiate_auth(
            UserPoolId=USER_POOL_ID,
            ClientId=WEB_CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password,
            }
        )

        auth_result = resp.get('AuthenticationResult', {})
        id_token = auth_result.get('IdToken', '')

        if not id_token:
            return None

        import base64 as b64
        try:
            payload = id_token.split('.')[1]
            padded = payload + '=' * (4 - len(payload) % 4)
            decoded = b64.urlsafe_b64decode(padded)
            claims = json.loads(decoded)
            return {
                'sub': claims.get('sub', ''),
                'email': claims.get('email', username),
                'token': id_token,
            }
        except Exception:
            return {
                'sub': username,
                'email': username,
                'token': id_token,
            }

    except cognito.exceptions.NotAuthorizedException:
        logger.warning(f'Authentication failed for {username}')
        return None
    except Exception as e:
        logger.error(f'Auth error: {e}')
        return None


def parse_body(event: Dict) -> Dict:
    try:
        if event.get('body'):
            return json.loads(event['body'])
        return {}
    except (json.JSONDecodeError, TypeError):
        return {}


def get_method(event: Dict) -> str:
    http_method = event.get('httpMethod', 'GET').upper()
    query_params = event.get('queryStringParameters') or {}
    query_method = query_params.get('method', '').upper()

    if query_method:
        return query_method

    if http_method == 'POST':
        body = parse_body(event)
        return body.get('method', http_method)

    return http_method


def lambda_handler(event: Dict, context) -> Dict:
    logger.info(f'Event: {json.dumps(event)}')

    if event.get('httpMethod') == 'OPTIONS':
        return response(200, {'success': True})

    user = authenticate(event)
    if not user:
        return response(401, {'error': 'Authentication required'})

    sub = user['sub']
    email = user['email']
    method = get_method(event)

    body = parse_body(event)
    path = body.get('path', '')
    if not path:
        query_params = event.get('queryStringParameters') or {}
        path = query_params.get('path', '/')

    logger.info(f'WebDAV method={method} path={path} user={email}')

    try:
        if method == 'PROPFIND':
            return handle_propfind(sub, path)
        elif method == 'MKCOL':
            return handle_mkcol(sub, path, body)
        elif method == 'MOVE':
            dest = body.get('destination', '')
            if not dest:
                dest = event.get('headers', {}).get('Destination', '')
            return handle_move(sub, path, dest)
        elif method == 'GET':
            return handle_get(sub, path)
        elif method == 'PUT':
            return handle_put(sub, path, body, event)
        elif method == 'DELETE':
            return handle_delete(sub, path)
        else:
            return response(405, {'error': f'Method {method} not supported'})

    except Exception as e:
        logger.error(f'Error processing {method} {path}: {e}', exc_info=True)
        return response(500, {'error': 'Internal server error'})


def resolve_path(sub: str, path: str) -> tuple:
    folders_table = dynamodb.Table(FOLDERS_TABLE)
    files_table = dynamodb.Table(FILES_TABLE)

    path = path.strip('/')
    if not path:
        return 'root', None, None

    parts = path.split('/')
    current_parent = 'root'
    current_name = parts[-1]

    if len(parts) > 1:
        parent_path = '/'.join(parts[:-1])
        parent_resp = folders_table.query(
            KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#'),
            FilterExpression=Attr('name').eq(parent_path.split('/')[-1]) & Attr('parentId').eq('root')
        )
        folders = parent_resp.get('Items', [])
        if folders:
            current_parent = folders[0]['folderId']

    file_resp = files_table.query(
        KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FILE#'),
        FilterExpression=Attr('fileName').eq(current_name) & Attr('isDeleted').eq(False)
    )
    files = file_resp.get('Items', [])

    folder_resp = folders_table.query(
        KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#'),
        FilterExpression=Attr('name').eq(current_name) & Attr('parentId').eq(current_parent)
    )
    folders = folder_resp.get('Items', [])

    return current_parent, files[0] if files else None, folders[0] if folders else None


def handle_propfind(sub: str, path: str) -> Dict:
    files_table = dynamodb.Table(FILES_TABLE)
    folders_table = dynamodb.Table(FOLDERS_TABLE)

    path = path.strip('/')
    parent_id = 'root'
    folder_name = ''

    if path:
        parts = path.split('/')
        folder_name = parts[-1]
        folders_resp = folders_table.query(
            KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#'),
            FilterExpression=Attr('name').eq(folder_name)
        )
        folders = folders_resp.get('Items', [])
        if folders:
            parent_id = folders[0]['folderId']
        else:
            parent_id = path.replace('/', '_')

    folder_resp = folders_table.query(
        KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#'),
        FilterExpression=Attr('parentId').eq(parent_id)
    )
    subfolders = folder_resp.get('Items', [])

    file_resp = files_table.query(
        KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FILE#'),
        FilterExpression=Attr('folderId').eq(parent_id) & Attr('isDeleted').eq(False)
    )
    files = file_resp.get('Items', [])

    result = {
        'path': f'/{path}' if path else '/',
        'folders': [{'name': f['name'], 'folderId': f['folderId']} for f in subfolders],
        'files': [{'name': f['fileName'], 'fileId': f['fileId'], 'size': f.get('size', 0), 'contentType': f.get('contentType', '')} for f in files],
    }

    return response(200, result)


def handle_mkcol(sub: str, path: str, body: Dict) -> Dict:
    folders_table = dynamodb.Table(FOLDERS_TABLE)
    path = path.strip('/')
    if not path:
        return response(400, {'error': 'Path is required'})

    parts = path.split('/')
    folder_name = parts[-1]
    parent_id = 'root'

    if len(parts) > 1:
        parent_path = parts[:-1]
        parent_resp = folders_table.query(
            KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#'),
            FilterExpression=Attr('name').eq(parent_path[-1]) & Attr('parentId').eq('root')
        )
        parents = parent_resp.get('Items', [])
        if parents:
            parent_id = parents[0]['folderId']

    existing = folders_table.query(
        KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#'),
        FilterExpression=Attr('name').eq(folder_name) & Attr('parentId').eq(parent_id)
    )
    if existing.get('Items'):
        return response(409, {'error': 'Folder already exists'})

    import uuid
    folder_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    item = {
        'PK': sub,
        'SK': f'FOLDER#{folder_id}',
        'folderId': folder_id,
        'name': folder_name,
        'parentId': parent_id,
        'owner': sub,
        'ownerEmail': body.get('email', ''),
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
        return response(201, {'success': True, 'folderId': folder_id})
    except Exception as e:
        logger.error(f'Error creating folder: {e}')
        return response(500, {'error': 'Failed to create folder'})


def handle_move(sub: str, source_path: str, dest_path: str) -> Dict:
    if not source_path or not dest_path:
        return response(400, {'error': 'Source and destination paths are required'})

    files_table = dynamodb.Table(FILES_TABLE)
    folders_table = dynamodb.Table(FOLDERS_TABLE)

    source_name = source_path.strip('/').split('/')[-1]
    dest_name = dest_path.strip('/').split('/')[-1]

    _, file_item, folder_item = resolve_path(sub, source_path)

    if file_item:
        new_folder_id = 'root'
        dest_parts = dest_path.strip('/').split('/')
        if len(dest_parts) > 1:
            parent_resp = folders_table.query(
                KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#'),
                FilterExpression=Attr('name').eq(dest_parts[-2]) & Attr('parentId').eq('root')
            )
            parents = parent_resp.get('Items', [])
            if parents:
                new_folder_id = parents[0]['folderId']

        old_key = file_item.get('s3Key', '')
        new_key = f'{USERS_PREFIX}{sub}/{new_folder_id}/{file_item["fileId"]}_{dest_name}'

        if old_key:
            try:
                s3.copy_object(Bucket=BUCKET, CopySource={'Bucket': BUCKET, 'Key': old_key}, Key=new_key)
                s3.delete_object(Bucket=BUCKET, Key=old_key)
            except Exception as e:
                logger.error(f'Failed to move S3 object: {e}')

        now = datetime.now(timezone.utc).isoformat()
        files_table.update_item(
            Key={'PK': sub, 'SK': f'FILE#{file_item["fileId"]}'},
            UpdateExpression='SET fileName = :name, folderId = :fid, s3Key = :key, updatedAt = :now',
            ExpressionAttributeValues={
                ':name': dest_name,
                ':fid': new_folder_id,
                ':key': new_key,
                ':now': now,
            }
        )
        return response(200, {'success': True, 'type': 'file'})

    if folder_item:
        now = datetime.now(timezone.utc).isoformat()
        folders_table.update_item(
            Key={'PK': sub, 'SK': f'FOLDER#{folder_item["folderId"]}'},
            UpdateExpression='SET #name = :name, updatedAt = :now',
            ExpressionAttributeNames={'#name': 'name'},
            ExpressionAttributeValues={':name': dest_name, ':now': now},
        )
        return response(200, {'success': True, 'type': 'folder'})

    return response(404, {'error': 'Path not found'})


def handle_get(sub: str, path: str) -> Dict:
    path = path.strip('/')
    if not path:
        return response(400, {'error': 'Path is required'})

    _, file_item, _ = resolve_path(sub, path)
    if not file_item:
        return response(404, {'error': 'File not found'})

    file_key = file_item.get('s3Key', '')
    if not file_key:
        return response(404, {'error': 'File key not found'})

    try:
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET, 'Key': file_key},
            ExpiresIn=3600
        )
    except Exception as e:
        logger.error(f'Failed to generate presigned URL: {e}')
        return response(500, {'error': 'Failed to generate download URL'})

    return response(302, {
        'success': True,
        'redirectUrl': presigned_url,
        'fileName': file_item.get('fileName', ''),
        'contentType': file_item.get('contentType', ''),
    })


def handle_put(sub: str, path: str, body: Dict, event: Dict) -> Dict:
    files_table = dynamodb.Table(FILES_TABLE)
    folders_table = dynamodb.Table(FOLDERS_TABLE)

    path = path.strip('/')
    if not path:
        return response(400, {'error': 'Path is required'})

    parts = path.split('/')
    file_name = parts[-1]
    folder_id = 'root'

    if len(parts) > 1:
        folder_path = parts[:-1]
        current_parent = 'root'
        for folder_name in folder_path:
            folders_resp = folders_table.query(
                KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#'),
                FilterExpression=Attr('name').eq(folder_name) & Attr('parentId').eq(current_parent)
            )
            existing = folders_resp.get('Items', [])
            if existing:
                current_parent = existing[0]['folderId']
            else:
                import uuid
                new_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                folders_table.put_item(Item={
                    'PK': sub,
                    'SK': f'FOLDER#{new_id}',
                    'folderId': new_id,
                    'name': folder_name,
                    'parentId': current_parent,
                    'owner': sub,
                    'ownerEmail': '',
                    'createdAt': now,
                    'updatedAt': now,
                    'isShared': False,
                    'shareToken': '',
                    'sharePin': '',
                    'shareExpiry': '',
                    'sharePermission': '',
                    'sharedWithEmails': [],
                })
                current_parent = new_id
        folder_id = current_parent

    import uuid
    file_id = str(uuid.uuid4()).replace('-', '')[:20]
    content_type = body.get('contentType', 'application/octet-stream')
    size = body.get('size', 0)
    s3_key = f'{USERS_PREFIX}{sub}/{folder_id}/{file_id}_{file_name}'

    try:
        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={'Bucket': BUCKET, 'Key': s3_key, 'ContentType': content_type},
            ExpiresIn=3600
        )
    except Exception as e:
        logger.error(f'Failed to generate presigned URL: {e}')
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
        'ownerEmail': '',
        's3Key': s3_key,
        'isDeleted': False,
        'deletedAt': '',
        'createdAt': now,
        'updatedAt': now,
    }

    try:
        files_table.put_item(Item=item)
        return response(201, {'success': True, 'file': item, 'uploadUrl': presigned_url})
    except Exception as e:
        logger.error(f'Error saving file: {e}')
        return response(500, {'error': 'Failed to save file'})


def handle_delete(sub: str, path: str) -> Dict:
    files_table = dynamodb.Table(FILES_TABLE)
    folders_table = dynamodb.Table(FOLDERS_TABLE)

    _, file_item, folder_item = resolve_path(sub, path.strip('/'))

    if file_item:
        s3_key = file_item.get('s3Key', '')
        if s3_key:
            try:
                s3.delete_object(Bucket=BUCKET, Key=s3_key)
            except Exception:
                pass
        files_table.delete_item(Key={'PK': sub, 'SK': f'FILE#{file_item["fileId"]}'})
        return response(200, {'success': True, 'type': 'file'})

    if folder_item:
        folder_id = folder_item['folderId']
        child_files = files_table.query(
            KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FILE#'),
            FilterExpression=Attr('folderId').eq(folder_id)
        ).get('Items', [])
        for cf in child_files:
            cf_key = cf.get('s3Key', '')
            if cf_key:
                try:
                    s3.delete_object(Bucket=BUCKET, Key=cf_key)
                except Exception:
                    pass
            files_table.delete_item(Key={'PK': sub, 'SK': f'FILE#{cf["fileId"]}'})

        child_folders = folders_table.query(
            KeyConditionExpression=Key('PK').eq(sub) & Key('SK').begins_with('FOLDER#'),
            FilterExpression=Attr('parentId').eq(folder_id)
        ).get('Items', [])
        for cf in child_folders:
            folders_table.delete_item(Key={'PK': sub, 'SK': f'FOLDER#{cf["folderId"]}'})

        folders_table.delete_item(Key={'PK': sub, 'SK': f'FOLDER#{folder_id}'})
        return response(200, {'success': True, 'type': 'folder'})

    return response(404, {'error': 'Path not found'})
