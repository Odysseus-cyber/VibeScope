from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    data_mode: str = "demo"
    database_url: str = "sqlite:///./vibescope-demo.db"
    github_token: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    tracking_limit: int = 1000
    daily_classification_limit: int = 100
    warehouse_enabled: bool = False
    warehouse_dir: str = str(Path(__file__).resolve().parents[2] / "warehouse")
    evaluation_dir: str = str(
        Path(__file__).resolve().parents[2] / "data" / "evaluation"
    )
    cors_origins: str = (
        "http://localhost:5180,http://127.0.0.1:5180,http://localhost:5173,http://127.0.0.1:5173"
    )

    @model_validator(mode="after")
    def validate_mode(self):
        if self.data_mode not in ("demo", "live"):
            raise ValueError("DATA_MODE must be demo or live")
        if (
            self.data_mode == "live"
            and self.database_url == "sqlite:///./vibescope-demo.db"
        ):
            raise ValueError(
                "Live mode requires an explicitly configured separate DATABASE_URL"
            )
        return self


settings = Settings()
