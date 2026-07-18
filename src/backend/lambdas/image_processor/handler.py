import json
import os
import io
import logging
from typing import Any, Dict

import boto3
from PIL import Image

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

s3 = boto3.client('s3')

BUCKET = os.environ.get('BUCKET_NAME', '')
USERS_PREFIX = os.environ.get('USERS_PREFIX', 'users/')
THUMBNAIL_PREFIX = os.environ.get('THUMBNAIL_PREFIX', 'thumbnails/')
THUMBNAIL_SIZE = int(os.environ.get('THUMBNAIL_SIZE', 200))


def lambda_handler(event: Dict, context) -> Dict:
    logger.info(f'Processing event: {json.dumps(event)}')

    try:
        for record in event.get('Records', []):
            try:
                process_record(record)
            except Exception as e:
                logger.error(f'Error processing record: {e}', exc_info=True)

        return {'statusCode': 200, 'body': json.dumps({'success': True})}
    except Exception as e:
        logger.error(f'Unhandled error: {e}', exc_info=True)
        return {'statusCode': 200, 'body': json.dumps({'success': True, 'warning': str(e)})}


def process_record(record: Dict):
    event_name = record.get('eventName', '')
    if 'ObjectCreated' not in event_name:
        logger.info(f'Skipping non-create event: {event_name}')
        return

    s3_event = record.get('s3', {})
    bucket = s3_event.get('bucket', {}).get('name', '')
    key = s3_event.get('object', {}).get('key', '')

    if not bucket or not key:
        logger.warning('Missing bucket or key in event')
        return

    logger.info(f'Processing object: s3://{bucket}/{key}')

    if not key.startswith(USERS_PREFIX):
        logger.info(f'Skipping non-user object: {key}')
        return

    if THUMBNAIL_PREFIX and key.startswith(THUMBNAIL_PREFIX):
        logger.info(f'Skipping thumbnail object: {key}')
        return

    if 'trash/' in key:
        logger.info(f'Skipping trashed object: {key}')
        return

    try:
        head_resp = s3.head_object(Bucket=bucket, Key=key)
        content_type = head_resp.get('ContentType', '')
    except Exception as e:
        logger.warning(f'Could not head object: {e}')
        content_type = ''

    if not content_type or not content_type.startswith('image/'):
        logger.info(f'Skipping non-image ({content_type}): {key}')
        return

    thumb_suffix = key[len(USERS_PREFIX):] if key.startswith(USERS_PREFIX) else key
    thumb_key = f'{THUMBNAIL_PREFIX}{thumb_suffix}'

    try:
        s3.head_object(Bucket=BUCKET, Key=thumb_key)
        logger.info(f'Thumbnail already exists: {thumb_key}')
        return
    except Exception:
        pass

    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
        image_data = resp['Body'].read()
    except Exception as e:
        logger.error(f'Failed to read image from S3: {e}')
        return

    try:
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.LANCZOS)

        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        buffer.seek(0)

        s3.put_object(
            Bucket=BUCKET,
            Key=thumb_key,
            Body=buffer,
            ContentType='image/jpeg',
            Metadata={
                'original': key,
                'generated': 'thumbnail',
            }
        )
        logger.info(f'Thumbnail created: {thumb_key} (from {key})')
    except Exception as e:
        logger.error(f'Failed to generate thumbnail for {key}: {e}')
