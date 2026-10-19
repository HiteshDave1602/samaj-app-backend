from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    # Fernet key: encrypts TOTP secrets at rest and signs the login->MFA ticket.
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    fernet_key: str
    # HMAC key for member.mobile_hash / otp_challenge.mobile_hash. Changing it orphans every stored hash.
    # Generate: python -c "import secrets; print(secrets.token_hex(32))"
    mobile_pepper: str
    media_dir: str = "media"  # uploaded news/ad images
    private_dir: str = "private"  # ID documents, matrimony photos, import files; encrypted, never served directly


settings = Settings()
