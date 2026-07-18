import json
import logging
import os
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

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

def generate_file_id() -> str:
    return str(uuid.uuid4()).replace('-', '')[:20]

def generate_folder_id() -> str:
    return str(uuid.uuid4())

def get_file_icon(file_type: Optional[str], file_name: str) -> str:
    if not file_type:
        return '📄'
    if file_type.startswith('image/'):
        return '📷'
    if file_type.startswith('video/'):
        return '🎬'
    if file_type.startswith('audio/'):
        return '🎵'
    if 'pdf' in file_type:
        return '📕'
    if any(t in file_type for t in ['text', 'json', 'javascript']):
        return '📄'
    if any(t in file_type for t in ['zip', 'rar', 'tar', 'gzip']):
        return '📦'
    return '📄'

def format_bytes(bytes_val: int) -> str:
    if not bytes_val:
        return '0 B'
    sizes = ['B', 'KB', 'MB', 'GB']
    i = 0
    while bytes_val >= 1024 and i < len(sizes) - 1:
        bytes_val /= 1024
        i += 1
    return f'{bytes_val:.1f} {sizes[i]}'
