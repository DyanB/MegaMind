"""
AWS S3 Service for PDF storage
"""
import boto3
from botocore.exceptions import ClientError
from typing import Optional, BinaryIO
import os
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class S3Service:
    """Service for managing PDF documents in AWS S3"""
    
    def __init__(self):
        """Initialize S3 client with credentials from environment"""
        self.bucket_name = os.getenv("AWS_S3_BUCKET", "wandai-documents")
        self.region = os.getenv("AWS_REGION", "us-east-1")
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=self.region
        )
        
        logger.info(f"S3Service initialized for bucket: {self.bucket_name}")
    
    def upload_pdf(
        self,
        file_content: bytes,
        s3_key: str,
        metadata: Optional[dict] = None
    ) -> dict:
        """
        Upload a PDF file to S3
        
        Args:
            file_content: Binary content of the PDF
            s3_key: S3 object key (path in bucket), e.g. "pdfs/doc123.pdf"
            metadata: Optional metadata dict to attach to the file
        
        Returns:
            dict with s3_key, bucket, region, size
        """
        try:
            # Upload file
            extra_args = {
                'ContentType': 'application/pdf',
                'ServerSideEncryption': 'AES256'  # Enable encryption at rest
            }
            
            if metadata:
                # Convert metadata values to strings (S3 requirement)
                extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                **extra_args
            )
            
            logger.info(f"✅ Uploaded PDF to S3: {s3_key}")
            
            return {
                "s3_key": s3_key,
                "bucket": self.bucket_name,
                "region": self.region,
                "size": len(file_content)
            }
        
        except ClientError as e:
            logger.error(f"❌ S3 upload failed: {e}")
            raise Exception(f"Failed to upload to S3: {str(e)}")
    
    def get_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate a presigned URL for temporary access to a PDF
        
        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default 1 hour)
        
        Returns:
            Presigned URL string
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            
            logger.info(f"Generated presigned URL for: {s3_key}")
            return url
        
        except ClientError as e:
            logger.error(f"❌ Failed to generate presigned URL: {e}")
            raise Exception(f"Failed to generate presigned URL: {str(e)}")
    
    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3
        
        Args:
            s3_key: S3 object key to delete
        
        Returns:
            True if successful
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            logger.info(f"🗑️ Deleted from S3: {s3_key}")
            return True
        
        except ClientError as e:
            logger.error(f"❌ S3 deletion failed: {e}")
            return False
    
    def file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in S3
        
        Args:
            s3_key: S3 object key to check
        
        Returns:
            True if file exists
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return True
        except ClientError:
            return False
    
    def get_file_metadata(self, s3_key: str) -> Optional[dict]:
        """
        Get metadata for a file in S3
        
        Args:
            s3_key: S3 object key
        
        Returns:
            Metadata dict or None if not found
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            return {
                "size": response.get('ContentLength'),
                "last_modified": response.get('LastModified'),
                "content_type": response.get('ContentType'),
                "metadata": response.get('Metadata', {})
            }
        
        except ClientError as e:
            logger.error(f"Failed to get metadata: {e}")
            return None
