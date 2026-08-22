from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────
    secret_key: str = "change-me-in-production"
    base_url: str = "http://localhost:8000"
    data_folder: str = "static"
    allowed_origins: list[str] = ["https://app.tlacua.cloud", "https://api.tlacua.cloud"]

    # ── Database ──────────────────────────────────────────
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "llmlab"
    db_user: str = "postgres"
    db_password: str = ""

    # ── MinIO ─────────────────────────────────────────────
    minio_endpoint: str = "storage.tlacua.cloud"
    minio_access_key: str = "admin"
    minio_secret_key: str = ""
    minio_secure: bool = True
    minio_bucket: str = "llm-lab"

    # ── OAuth — Google ────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""

    # ── OAuth — Facebook ──────────────────────────────────
    facebook_client_id: str = ""
    facebook_client_secret: str = ""

    # ── Internal API key ──────────────────────────────────
    internal_secret_key: str = ""

    # ── LLM ───────────────────────────────────────────────
    default_model: str = "claude-sonnet-4-6"


settings = Settings()
