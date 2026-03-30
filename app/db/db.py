import os
from typing import Any, Dict, Optional

from app.core.settings import get_settings


def _get_secret_creds(secret_name: str, region: str) -> Optional[Dict[str, Any]]:
    """
    Fetch DB creds from SecretCache if available.

    Expected SecretCache output keys:
      host, user, password, database
    """
    try:
        from app.utils import SecretCache

        sm = SecretCache(region=region)
        return sm.get(secret_name)
    except Exception:
        return None


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

    # Prefer SecretCache if present (production style).
    secret_name = os.getenv("MYSQL_SECRET_NAME", "MySQL_local")
    region = os.getenv("SECRET_REGION", "us-east-1")
    secret_creds = _get_secret_creds(secret_name=secret_name, region=region)

    s = get_settings()
    host = (secret_creds or {}).get("host") or s.mysql_host
    user = (secret_creds or {}).get("user") or s.mysql_user
    password = (secret_creds or {}).get("password") or s.mysql_password
    database = (secret_creds or {}).get("database") or s.mysql_db
    port = int((secret_creds or {}).get("port") or s.mysql_port)

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
    )
