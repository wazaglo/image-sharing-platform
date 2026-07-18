import json
import os
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

FOLDERS_TABLE = os.environ.get('FOLDERS_TABLE', 'Folders')
SHARES_TABLE = os.environ.get('SHARES_TABLE', 'Shares')
CLOUDFRONT_DOMAIN = os.environ.get('CLOUDFRONT_DOMAIN', '')
BUCKET = os.environ.get('BUCKET_NAME', '')

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

def lambda_handler(event: Dict, context) -> Dict:
    logger.info(f'Event: {json.dumps(event)}')
    try:
        sub, email = get_user_from_event(event)
        if not sub:
            return response(401, {'error': 'Unauthorized'})

        body = parse_body(event)
        folder_id = body.get('folderId', '')
        if not folder_id:
            return response(400, {'error': 'folderId is required'})

        folders_table = dynamodb.Table(FOLDERS_TABLE)
        folder_resp = folders_table.get_item(Key={'PK': sub, 'SK': f'FOLDER#{folder_id}'})
        folder = folder_resp.get('Item')

        if not folder:
            return response(404, {'error': 'Folder not found'})

        if folder.get('owner') != sub:
            return response(403, {'error': 'You do not own this folder'})

        share_token = str(uuid.uuid4()).replace('-', '')[:16]
        pin = body.get('pin', '')
        expiry = body.get('expiry', '')
        permission = body.get('permission', 'view')
        shared_with_emails = body.get('sharedWithEmails', [])

        share_pin_hash = ''
        if pin:
            share_pin_hash = hashlib.sha256(pin.encode()).hexdigest()

        share_url = f'https://{CLOUDFRONT_DOMAIN}/share/{share_token}' if CLOUDFRONT_DOMAIN else f'/share/{share_token}'

        now = datetime.now(timezone.utc).isoformat()

        share_item = {
            'PK': sub,
            'SK': f'SHARE#{share_token}',
            'shareToken': share_token,
            'folderId': folder_id,
            'folderName': folder.get('name', ''),
            'pinHash': share_pin_hash,
            'expiry': expiry,
            'permission': permission,
            'sharedWithEmails': shared_with_emails if isinstance(shared_with_emails, list) else [],
            'createdAt': now,
            'updatedAt': now,
        }

        try:
            shares_table = dynamodb.Table(SHARES_TABLE)
            shares_table.put_item(Item=share_item)
        except Exception as e:
            logger.error(f'Error saving share: {e}')
            return response(500, {'error': 'Failed to create share link'})

        try:
            folders_table.update_item(
                Key={'PK': sub, 'SK': f'FOLDER#{folder_id}'},
                UpdateExpression=(
                    'SET isShared = :true, shareToken = :token, '
                    'sharePin = :pin, shareExpiry = :expiry, '
                    'sharePermission = :perm, sharedWithEmails = :emails, '
                    'updatedAt = :now'
                ),
                ExpressionAttributeValues={
                    ':true': True,
                    ':token': share_token,
                    ':pin': share_pin_hash,
                    ':expiry': expiry,
                    ':perm': permission,
                    ':emails': shared_with_emails if isinstance(shared_with_emails, list) else [],
                    ':now': now,
                }
            )
        except Exception as e:
            logger.error(f'Error updating folder share info: {e}')

        logger.info(f'Share link created for folder {folder_id} by {email}: {share_token}')
        return response(200, {
            'success': True,
            'shareToken': share_token,
            'shareUrl': share_url,
            'hasPin': bool(pin),
            'expiry': expiry,
            'permission': permission,
        })

    except Exception as e:
        logger.error(f'Unhandled error: {str(e)}', exc_info=True)
        return response(500, {'error': 'Internal server error'})
