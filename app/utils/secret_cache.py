import json
import time
from typing import Any, Dict, Tuple

import boto3
from botocore.exceptions import ClientError


class SecretCache:
    """
    Caches AWS Secrets Manager secrets.

    - JSON secrets are returned as dictionaries
    - non-JSON secrets are returned as {"value": secret}
    """

    def __init__(self, region: str = "us-east-1", ttl_seconds: int = 300):
        self.client = boto3.client("secretsmanager", region_name=region)
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def get(self, secret_id: str) -> Dict[str, Any]:
        now = time.time()
        ent = self._cache.get(secret_id)
        if ent and ent[0] > now:
            return ent[1]

        try:
            resp = self.client.get_secret_value(SecretId=secret_id)
        except ClientError as e:
            raise RuntimeError(f"Secrets Manager error for {secret_id}: {e}") from e

        val = resp.get("SecretString") or resp["SecretBinary"].decode("utf-8")
        try:
            parsed = json.loads(val)
        except json.JSONDecodeError:
            parsed = {"value": val}

        self._cache[secret_id] = (now + self.ttl_seconds, parsed)
        return parsed
