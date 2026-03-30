import os
from typing import Any, Dict, Optional
import boto3
import json
import time
from botocore.exceptions import ClientError

DB_NAME = None
class SecretCache:
    """
    Caches AWS Secrets Manager secrets.
    Parses JSON secrets into dictionaries; non-JSON secrets are returned as {"value": secret}."""

    def __init__(self, region="us-east-1"):
        self.client = boto3.client("secretsmanager", region_name=region)
        self._cache = {}  # {secret_id: (expires_at, parsed_value)}

    def get(self, secret_id: str):
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

        self._cache[secret_id] = (parsed)
        return parsed



def get_connection():
    """
    Return a new pymysql connection (no SQLAlchemy DB URL).

    Credentials source order:
    1) `utils.SecretCache` (if present)
    2) environment variables (MYSQL_HOST/USER/PASSWORD/DB)
    """
    try:
        import pymysql
    except Exception as e:
        raise RuntimeError(
            "Missing MySQL driver `pymysql`. Install it with `pip install pymysql`."
        ) from e

    sm = SecretCache(region="us-east-1")
    db_creds = sm.get("MySQL_local")
    DB_HOST = db_creds.get("host")
    DB_USER = db_creds.get("user")
    DB_PASSWORD = db_creds.get("password")
    DB_NAME = db_creds.get("database")
    print("Establishing database connection...")
    print(f"DB Host: {DB_HOST}, DB User: {DB_USER}, DB Name: {DB_NAME}")
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    return connection

if __name__ == "__main__":
    # Test the connection function
    try:
        conn = get_connection()
        print("Database connection successful!")
        conn.close()
    except Exception as e:
        print(f"Database connection failed: {e}")
