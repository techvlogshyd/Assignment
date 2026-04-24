import os


class Settings:
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "fallback-dev-secret")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24


settings = Settings()
