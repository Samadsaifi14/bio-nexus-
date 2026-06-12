import os
import json
import uuid
from datetime import datetime
from typing import Optional
from app.config import settings

_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "raw_store")
R2_ENABLED = all([
    os.getenv("R2_ACCOUNT_ID"),
    os.getenv("R2_ACCESS_KEY_ID"),
    os.getenv("R2_SECRET_ACCESS_KEY"),
])


async def store_raw_response(
    job_id: str,
    step: str,
    service: str,
    data: str,
    fmt: str = "xml",
) -> str:
    key = f"raw/{job_id}/{step}-{service}.{fmt}"
    if R2_ENABLED:
        return await _store_r2(key, data)
    return _store_local(key, data)


async def store_result(
    job_id: str,
    result_type: str,
    data: dict,
    fmt: str = "json",
) -> str:
    key = f"results/{job_id}/{result_type}.{fmt}"
    payload = json.dumps(data)
    if R2_ENABLED:
        return await _store_r2(key, payload)
    return _store_local(key, payload)


def _store_local(key: str, data: str) -> str:
    path = os.path.join(_STORE_DIR, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    return path


async def _store_r2(key: str, data: str) -> str:
    try:
        import boto3
        from botocore.config import Config
        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
        )
        bucket = os.getenv("R2_BUCKET_NAME", "bioflow-raw-responses")
        s3.put_object(Bucket=bucket, Key=key, Body=data.encode(), ContentType="text/plain")
        return f"r2://{bucket}/{key}"
    except Exception as e:
        return _store_local(key, data)


def get_stored_response(path_or_key: str) -> Optional[str]:
    if path_or_key.startswith("r2://"):
        return None
    if os.path.exists(path_or_key):
        with open(path_or_key, "r", encoding="utf-8") as f:
            return f.read()
    return None
