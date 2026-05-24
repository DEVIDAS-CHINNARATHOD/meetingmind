"""
config/settings.py — Phase 2
Central configuration loaded from environment variables.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",
                                      case_sensitive=False, extra="ignore")
    # Application
    app_env: Literal["development","production","test"] = "development"
    app_name: str = "MeetingMind AI"
    app_version: str = "2.0.0"
    secret_key: str
    debug: bool = False
    allowed_origins: list[str] = ["http://localhost:3000"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v):
        return [o.strip() for o in v.split(",")] if isinstance(v,str) else v

    # Database
    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # AI / LLM
    groq_api_key: str
    openai_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fallback_model: str = "deepseek-r1-distill-llama-70b"
    whisper_model_size: str = "large-v3"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # Phase 2: Diarization
    huggingface_token: str = ""
    diarization_enabled: bool = True

    # Vector DB
    chroma_db_path: str = "./data/chromadb"
    chroma_collection_transcripts: str = "meeting_transcripts"
    embedding_model: str = "all-MiniLM-L6-v2"

    # Storage
    storage_backend: Literal["local","s3","r2"] = "local"
    local_storage_path: str = "./data/uploads"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_bucket_name: str = ""
    aws_region: str = "ap-south-1"
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60

    # File upload
    max_upload_size_mb: int = 2048
    allowed_audio_formats: list[str] = ["mp3","wav","m4a","ogg","flac"]
    allowed_video_formats: list[str] = ["mp4","mkv","mov","avi","webm"]

    @field_validator("allowed_audio_formats","allowed_video_formats", mode="before")
    @classmethod
    def parse_formats(cls, v):
        return [f.strip().lower() for f in v.split(",")] if isinstance(v,str) else v

    # Phase 4
    zoom_client_id: str = ""
    zoom_account_id: str = ""
    zoom_client_secret: str = ""
    zoom_webhook_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""

    @property
    def max_upload_size_bytes(self): return self.max_upload_size_mb * 1024 * 1024
    @property
    def all_allowed_formats(self): return self.allowed_audio_formats + self.allowed_video_formats
    @property
    def is_production(self): return self.app_env == "production"
    @property
    def data_dir(self): return Path("./data")


@lru_cache(maxsize=1)
def get_settings() -> Settings: return Settings()

settings = get_settings()
# ← this append adds Phase 4 fields to Settings class
