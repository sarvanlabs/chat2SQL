import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # LLM
    ollama_url: str
    ollama_model: str

    # MySQL
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_db: str

    @property
    def database_url(self) -> str:
        # Uses SQLAlchemy's MySQL dialect via pymysql.
        # Note: keep secrets in env vars; do not hardcode credentials.
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )


def get_settings() -> Settings:
    return Settings(
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3:8b"),
        mysql_host=os.getenv("MYSQL_HOST", "localhost"),
        mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
        mysql_user=os.getenv("MYSQL_USER", "root"),
        mysql_password=os.getenv("MYSQL_PASSWORD", "localpassword"),
        mysql_db=os.getenv("MYSQL_DB", "companydb"),
    )
