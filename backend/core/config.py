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
    # False: admin login is password-only (no TOTP step). ponytail: off until the SMS OTP system lands.
    admin_mfa: bool = True
    # True: member OTP verify accepts any 6-digit code. ponytail: dev-only until the SMS gateway lands; never in prod.
    otp_bypass: bool = False
    # True: /member/auth/otp/send returns the code so the app shows it on screen. Demo-only until the SMS gateway
    # lands: with it on, anyone who types a number can log in as that member. Never in prod.
    otp_show_code: bool = False
    otp_ttl_seconds: int = 60  # how long a member OTP stays valid
    media_dir: str = "media"  # uploaded news/ad images
    private_dir: str = "private"  # ID documents, matrimony photos, import files; encrypted, never served directly
    # Optional contact email for the free translation service; raises its daily allowance from 5,000 to 50,000 characters.
    translate_email: str = ""
    # Per API process: 15 = SQLAlchemy's default 5 + 10 overflow. Keep processes x total under Postgres max_connections.
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Search engine for the member directory and matrimony search. Empty URL: both run on Postgres, as before.
    # Postgres stays the source of truth; the index is rebuilt from it with `python -m search.reindex --rebuild`.
    elasticsearch_url: str = ""
    elasticsearch_username: str = ""  # the restricted samaj_backend user (deploy/elasticsearch/roles.yml), never elastic
    elasticsearch_password: str = ""
    elasticsearch_index_prefix: str = "samaj"  # must start with "samaj": the role only grants samaj* indices
    elasticsearch_ca_certs: str = ""  # TLS clusters (prod): path to the cluster's CA certificate
    elasticsearch_replicas: int = 0  # set at index creation; 0 for one dev node, 1+ in prod
    # Per API process. 40 = AnyIO's thread limit, the most ES requests one process can have in flight.
    elasticsearch_max_connections: int = 40
    search_rate_per_minute: int = 60  # per member per API process; 429 above it

    # Request limits (core/ratelimit.py), 429 above them. Per API process except the OTP-send ones (Postgres).
    member_rate_per_minute: int = 60  # every member API, per member (SRS)
    member_file_rate_per_minute: int = 300  # photo / ID file downloads, per member: list thumbnails
    admin_rate_per_minute: int = 300  # every admin API, per admin: dashboard pages fire several calls
    otp_ip_rate_per_minute: int = 10  # OTP send and verify, per client IP (SRS)
    otp_ip_rate_per_hour: int = 30  # OTP sends per client IP: stops a bot rotating numbers under the minute limit
    auth_ip_rate_per_minute: int = 10  # admin login / MFA, per client IP: stops guessing across many emails


settings = Settings()
