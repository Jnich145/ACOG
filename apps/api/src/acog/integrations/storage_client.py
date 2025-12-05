"""
S3/MinIO storage client for ACOG media assets.

This module provides a robust wrapper around boto3 for S3/MinIO operations with:
- Upload and download operations
- Pre-signed URL generation
- File existence checks
- Automatic content type detection
- Async and sync support
"""

import hashlib
import io
import logging
import mimetypes
from dataclasses import dataclass
from typing import Any, BinaryIO
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from acog.core.config import Settings, get_settings
from acog.core.exceptions import ExternalServiceError, NotFoundError

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """
    Result container for upload operations.

    Attributes:
        bucket: S3 bucket name
        key: S3 object key
        uri: Full S3 URI (s3://bucket/key)
        etag: S3 ETag for the uploaded object
        content_type: MIME type of the uploaded content
        file_size_bytes: Size of the uploaded file
        checksum_md5: MD5 hash of the uploaded content
    """

    bucket: str
    key: str
    uri: str
    etag: str
    content_type: str
    file_size_bytes: int
    checksum_md5: str

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for storage."""
        return {
            "bucket": self.bucket,
            "key": self.key,
            "uri": self.uri,
            "etag": self.etag,
            "content_type": self.content_type,
            "file_size_bytes": self.file_size_bytes,
            "checksum_md5": self.checksum_md5,
        }


class StorageClient:
    """
    S3/MinIO storage client for media asset management.

    Provides operations for:
    - Uploading bytes and files
    - Downloading content
    - Generating pre-signed URLs for direct access
    - Checking file existence
    - Deleting objects

    Example:
        ```python
        storage = StorageClient()

        # Upload audio file
        result = storage.upload_file(
            data=audio_bytes,
            bucket="acog-assets",
            key=f"episodes/{episode_id}/audio.mp3",
            content_type="audio/mpeg"
        )

        # Generate download URL
        url = storage.generate_presigned_url(
            bucket="acog-assets",
            key="episodes/123/audio.mp3",
            expires_in=3600
        )
        ```
    """

    def __init__(
        self,
        settings: Settings | None = None,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str | None = None,
    ) -> None:
        """
        Initialize the storage client.

        Args:
            settings: Application settings instance
            endpoint_url: S3/MinIO endpoint URL (overrides settings)
            access_key: S3 access key (overrides settings)
            secret_key: S3 secret key (overrides settings)
            region: AWS region (overrides settings)
        """
        self._settings = settings or get_settings()

        self._endpoint_url = endpoint_url or self._settings.s3_endpoint_url
        self._access_key = access_key or self._settings.s3_access_key
        self._secret_key = secret_key or self._settings.s3_secret_key
        self._region = region or self._settings.s3_region

        # Create boto3 client
        self._client = boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "adaptive"},
            ),
        )

        logger.debug(
            "Storage client initialized",
            extra={
                "endpoint_url": self._endpoint_url,
                "region": self._region,
            },
        )

    @property
    def default_assets_bucket(self) -> str:
        """Get the default bucket for assets."""
        return self._settings.s3_bucket_assets

    @property
    def default_scripts_bucket(self) -> str:
        """Get the default bucket for scripts."""
        return self._settings.s3_bucket_scripts

    def _calculate_md5(self, data: bytes) -> str:
        """Calculate MD5 hash of data."""
        return hashlib.md5(data).hexdigest()

    def _guess_content_type(self, key: str) -> str:
        """
        Guess content type from file extension.

        Args:
            key: S3 object key or filename

        Returns:
            MIME type string, defaults to application/octet-stream
        """
        content_type, _ = mimetypes.guess_type(key)
        return content_type or "application/octet-stream"

    def upload_file(
        self,
        data: bytes | BinaryIO,
        bucket: str,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """
        Upload data to S3/MinIO.

        Args:
            data: File content as bytes or file-like object
            bucket: S3 bucket name
            key: S3 object key (path within bucket)
            content_type: MIME type (auto-detected if not provided)
            metadata: Additional S3 metadata

        Returns:
            UploadResult with upload details

        Raises:
            ExternalServiceError: If upload fails
        """
        # Convert file-like to bytes if needed
        if hasattr(data, "read"):
            data = data.read()  # type: ignore

        # Ensure data is bytes
        if not isinstance(data, bytes):
            raise ValueError("Data must be bytes or a file-like object")

        # Auto-detect content type
        if content_type is None:
            content_type = self._guess_content_type(key)

        # Calculate checksum
        checksum = self._calculate_md5(data)

        # Prepare upload parameters
        extra_args: dict[str, Any] = {"ContentType": content_type}
        if metadata:
            extra_args["Metadata"] = metadata

        try:
            logger.info(
                "Uploading file to S3",
                extra={
                    "bucket": bucket,
                    "key": key,
                    "content_type": content_type,
                    "size_bytes": len(data),
                },
            )

            response = self._client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                **extra_args,
            )

            etag = response.get("ETag", "").strip('"')

            logger.info(
                "File uploaded successfully",
                extra={
                    "bucket": bucket,
                    "key": key,
                    "etag": etag,
                },
            )

            return UploadResult(
                bucket=bucket,
                key=key,
                uri=f"s3://{bucket}/{key}",
                etag=etag,
                content_type=content_type,
                file_size_bytes=len(data),
                checksum_md5=checksum,
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))

            logger.error(
                "S3 upload failed",
                extra={
                    "bucket": bucket,
                    "key": key,
                    "error_code": error_code,
                    "error": error_msg,
                },
            )

            raise ExternalServiceError(
                service="S3/MinIO",
                message=f"Failed to upload file to S3: {error_msg}",
                original_error=str(e),
            ) from e

    def upload_episode_asset(
        self,
        data: bytes,
        episode_id: UUID,
        asset_type: str,
        file_extension: str,
        content_type: str | None = None,
        version: int = 1,
    ) -> UploadResult:
        """
        Upload an asset for a specific episode with standard path format.

        Uses the standard path format: episodes/{episode_id}/{asset_type}_v{version}.{ext}

        Args:
            data: File content as bytes
            episode_id: UUID of the episode
            asset_type: Type of asset (audio, avatar_video, b_roll, etc.)
            file_extension: File extension without dot (mp3, mp4, etc.)
            content_type: MIME type (auto-detected if not provided)
            version: Version number for the asset

        Returns:
            UploadResult with upload details
        """
        key = f"episodes/{episode_id}/{asset_type}_v{version}.{file_extension}"

        return self.upload_file(
            data=data,
            bucket=self.default_assets_bucket,
            key=key,
            content_type=content_type,
            metadata={
                "episode_id": str(episode_id),
                "asset_type": asset_type,
                "version": str(version),
            },
        )

    def download_file(
        self,
        bucket: str,
        key: str,
    ) -> bytes:
        """
        Download file content from S3/MinIO.

        Args:
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            File content as bytes

        Raises:
            NotFoundError: If object does not exist
            ExternalServiceError: If download fails
        """
        try:
            logger.info(
                "Downloading file from S3",
                extra={
                    "bucket": bucket,
                    "key": key,
                },
            )

            response = self._client.get_object(Bucket=bucket, Key=key)
            data = response["Body"].read()

            logger.info(
                "File downloaded successfully",
                extra={
                    "bucket": bucket,
                    "key": key,
                    "size_bytes": len(data),
                },
            )

            return data

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))

            if error_code in ("NoSuchKey", "NoSuchBucket", "404"):
                logger.warning(
                    "S3 object not found",
                    extra={
                        "bucket": bucket,
                        "key": key,
                    },
                )
                raise NotFoundError(
                    resource_type="S3Object",
                    resource_id=f"{bucket}/{key}",
                ) from e

            logger.error(
                "S3 download failed",
                extra={
                    "bucket": bucket,
                    "key": key,
                    "error_code": error_code,
                    "error": error_msg,
                },
            )

            raise ExternalServiceError(
                service="S3/MinIO",
                message=f"Failed to download file from S3: {error_msg}",
                original_error=str(e),
            ) from e

    def download_to_stream(
        self,
        bucket: str,
        key: str,
    ) -> io.BytesIO:
        """
        Download file to a BytesIO stream.

        Args:
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            BytesIO object with file content
        """
        data = self.download_file(bucket, key)
        stream = io.BytesIO(data)
        stream.seek(0)
        return stream

    def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_in: int = 3600,
        method: str = "get_object",
    ) -> str:
        """
        Generate a pre-signed URL for direct access.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            expires_in: URL expiration time in seconds (default: 1 hour)
            method: S3 method (get_object or put_object)

        Returns:
            Pre-signed URL string

        Raises:
            ExternalServiceError: If URL generation fails
        """
        try:
            url = self._client.generate_presigned_url(
                ClientMethod=method,
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )

            logger.debug(
                "Generated pre-signed URL",
                extra={
                    "bucket": bucket,
                    "key": key,
                    "expires_in": expires_in,
                    "method": method,
                },
            )

            return url

        except ClientError as e:
            logger.error(
                "Failed to generate pre-signed URL",
                extra={
                    "bucket": bucket,
                    "key": key,
                    "error": str(e),
                },
            )

            raise ExternalServiceError(
                service="S3/MinIO",
                message="Failed to generate pre-signed URL",
                original_error=str(e),
            ) from e

    def generate_upload_url(
        self,
        bucket: str,
        key: str,
        content_type: str,
        expires_in: int = 3600,
    ) -> dict[str, str]:
        """
        Generate a pre-signed URL for direct upload.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            content_type: Expected content type
            expires_in: URL expiration time in seconds

        Returns:
            Dictionary with 'url' and 'fields' for multipart upload
        """
        try:
            response = self._client.generate_presigned_post(
                Bucket=bucket,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                ],
                ExpiresIn=expires_in,
            )

            logger.debug(
                "Generated pre-signed upload URL",
                extra={
                    "bucket": bucket,
                    "key": key,
                    "content_type": content_type,
                    "expires_in": expires_in,
                },
            )

            return response

        except ClientError as e:
            logger.error(
                "Failed to generate pre-signed upload URL",
                extra={
                    "bucket": bucket,
                    "key": key,
                    "error": str(e),
                },
            )

            raise ExternalServiceError(
                service="S3/MinIO",
                message="Failed to generate pre-signed upload URL",
                original_error=str(e),
            ) from e

    def file_exists(
        self,
        bucket: str,
        key: str,
    ) -> bool:
        """
        Check if a file exists in S3/MinIO.

        Args:
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            True if file exists, False otherwise
        """
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                return False
            # Re-raise for other errors
            raise ExternalServiceError(
                service="S3/MinIO",
                message="Failed to check file existence",
                original_error=str(e),
            ) from e

    def get_file_info(
        self,
        bucket: str,
        key: str,
    ) -> dict[str, Any]:
        """
        Get metadata about a file in S3/MinIO.

        Args:
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            Dictionary with file metadata

        Raises:
            NotFoundError: If object does not exist
        """
        try:
            response = self._client.head_object(Bucket=bucket, Key=key)

            return {
                "bucket": bucket,
                "key": key,
                "uri": f"s3://{bucket}/{key}",
                "content_type": response.get("ContentType"),
                "content_length": response.get("ContentLength"),
                "etag": response.get("ETag", "").strip('"'),
                "last_modified": response.get("LastModified"),
                "metadata": response.get("Metadata", {}),
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                raise NotFoundError(
                    resource_type="S3Object",
                    resource_id=f"{bucket}/{key}",
                ) from e
            raise ExternalServiceError(
                service="S3/MinIO",
                message="Failed to get file info",
                original_error=str(e),
            ) from e

    def delete_file(
        self,
        bucket: str,
        key: str,
    ) -> bool:
        """
        Delete a file from S3/MinIO.

        Args:
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            True if deletion was successful

        Raises:
            ExternalServiceError: If deletion fails
        """
        try:
            logger.info(
                "Deleting file from S3",
                extra={
                    "bucket": bucket,
                    "key": key,
                },
            )

            self._client.delete_object(Bucket=bucket, Key=key)

            logger.info(
                "File deleted successfully",
                extra={
                    "bucket": bucket,
                    "key": key,
                },
            )

            return True

        except ClientError as e:
            logger.error(
                "S3 delete failed",
                extra={
                    "bucket": bucket,
                    "key": key,
                    "error": str(e),
                },
            )

            raise ExternalServiceError(
                service="S3/MinIO",
                message="Failed to delete file from S3",
                original_error=str(e),
            ) from e

    def delete_episode_assets(
        self,
        episode_id: UUID,
    ) -> int:
        """
        Delete all assets for a specific episode.

        Args:
            episode_id: UUID of the episode

        Returns:
            Number of objects deleted
        """
        prefix = f"episodes/{episode_id}/"
        bucket = self.default_assets_bucket

        try:
            # List all objects with the prefix
            paginator = self._client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

            deleted_count = 0
            for page in pages:
                if "Contents" not in page:
                    continue

                objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
                if objects:
                    self._client.delete_objects(
                        Bucket=bucket,
                        Delete={"Objects": objects},
                    )
                    deleted_count += len(objects)

            logger.info(
                "Deleted episode assets",
                extra={
                    "episode_id": str(episode_id),
                    "deleted_count": deleted_count,
                },
            )

            return deleted_count

        except ClientError as e:
            logger.error(
                "Failed to delete episode assets",
                extra={
                    "episode_id": str(episode_id),
                    "error": str(e),
                },
            )

            raise ExternalServiceError(
                service="S3/MinIO",
                message="Failed to delete episode assets",
                original_error=str(e),
            ) from e

    def copy_file(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> UploadResult:
        """
        Copy a file within S3/MinIO.

        Args:
            source_bucket: Source bucket name
            source_key: Source object key
            dest_bucket: Destination bucket name
            dest_key: Destination object key

        Returns:
            UploadResult with destination details
        """
        try:
            copy_source = {"Bucket": source_bucket, "Key": source_key}

            response = self._client.copy_object(
                CopySource=copy_source,
                Bucket=dest_bucket,
                Key=dest_key,
            )

            # Get file info for the result
            head = self._client.head_object(Bucket=dest_bucket, Key=dest_key)

            return UploadResult(
                bucket=dest_bucket,
                key=dest_key,
                uri=f"s3://{dest_bucket}/{dest_key}",
                etag=response.get("CopyObjectResult", {}).get("ETag", "").strip('"'),
                content_type=head.get("ContentType", "application/octet-stream"),
                file_size_bytes=head.get("ContentLength", 0),
                checksum_md5=head.get("ETag", "").strip('"'),
            )

        except ClientError as e:
            raise ExternalServiceError(
                service="S3/MinIO",
                message="Failed to copy file in S3",
                original_error=str(e),
            ) from e

    def ensure_bucket_exists(self, bucket: str) -> None:
        """
        Ensure a bucket exists, creating it if necessary.

        Args:
            bucket: Bucket name to check/create
        """
        try:
            self._client.head_bucket(Bucket=bucket)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchBucket"):
                # Create the bucket
                create_params: dict[str, Any] = {"Bucket": bucket}
                if self._region and self._region != "us-east-1":
                    create_params["CreateBucketConfiguration"] = {
                        "LocationConstraint": self._region
                    }

                self._client.create_bucket(**create_params)
                logger.info(f"Created bucket: {bucket}")
            else:
                raise ExternalServiceError(
                    service="S3/MinIO",
                    message=f"Failed to access bucket: {bucket}",
                    original_error=str(e),
                ) from e


def get_storage_client(settings: Settings | None = None) -> StorageClient:
    """
    Factory function to create a storage client.

    Can be used as a FastAPI dependency.

    Args:
        settings: Optional settings override

    Returns:
        Configured StorageClient instance
    """
    return StorageClient(settings=settings)
