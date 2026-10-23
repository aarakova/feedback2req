from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="F2R_", extra="ignore")

    database_url: str
    allowed_origin: str = "http://localhost:8000"
    local_http: bool = False
    session_cookie: str = "f2r_session"
    session_seconds: int = Field(default=86400, ge=60)
    idle_seconds: int = Field(default=1800, ge=60)
    argon_time_cost: int = Field(default=3, ge=1)
    argon_memory_cost: int = Field(default=65536, ge=8192)
    argon_parallelism: int = Field(default=4, ge=1)
    max_body_bytes: int = Field(default=16384, ge=256)
    max_material_text_chars: int = Field(default=8192, ge=1)
    login_limit: int = Field(default=10, ge=1)
    login_window_seconds: int = Field(default=60, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)

    @model_validator(mode="after")
    def validate_transport(self):
        origin = urlsplit(self.allowed_origin)
        if origin.path or origin.query or origin.fragment or origin.username or not origin.hostname:
            raise ValueError("allowed_origin must be an exact origin without path or credentials")
        if origin.scheme != "https":
            if not (
                self.local_http
                and origin.scheme == "http"
                and origin.hostname in {"localhost", "127.0.0.1", "::1"}
            ):
                raise ValueError("HTTP requires local_http and a loopback origin")
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("PostgreSQL with Psycopg is required")
        return self
