import boto3
from botocore.exceptions import ClientError
from .config import get_settings

settings = get_settings()

s3_client = boto3.client(
    's3',
    endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
    aws_access_key_id=settings.MINIO_ROOT_USER,
    aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
    region_name='us-east-1'
)

def init_storage():
    """Crée le bucket s'il n'existe pas."""
    try:
        s3_client.head_bucket(Bucket=settings.MINIO_BUCKET)
    except ClientError:
        s3_client.create_bucket(Bucket=settings.MINIO_BUCKET)

def upload_file(file_content: bytes, object_name: str):
    """Upload un fichier dans MinIO."""
    s3_client.put_object(
        Bucket=settings.MINIO_BUCKET,
        Key=object_name,
        Body=file_content
    )
