import os
from dataclasses import dataclass, field
from typing import List

@dataclass
class Config:
    bucket_name: str = os.environ.get('BUCKET_NAME', '')
    users_prefix: str = os.environ.get('USERS_PREFIX', 'users/')
    trash_prefix: str = 'trash/'
    thumbnail_prefix: str = os.environ.get('THUMBNAIL_PREFIX', 'thumbnails/')
    folders_table_name: str = os.environ.get('FOLDERS_TABLE', 'Folders')
    files_table_name: str = os.environ.get('FILES_TABLE', 'Files')
    shares_table_name: str = os.environ.get('SHARES_TABLE', 'Shares')
    cloudfront_domain: str = os.environ.get('CLOUDFRONT_DOMAIN', '')
    user_pool_id: str = os.environ.get('USER_POOL_ID', '')
    web_client_id: str = os.environ.get('WEB_CLIENT_ID', '')
    admin_emails: List[str] = field(default_factory=lambda: os.environ.get('ADMIN_EMAILS', '').split(','))
    log_level: str = os.environ.get('LOG_LEVEL', 'INFO')
    presigned_url_expiry: int = 3600

config = Config()
