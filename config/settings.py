"""
Application Settings

Carga configuración desde variables de entorno usando Pydantic Settings.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings cargados desde .env
    """

    # ========== APPLICATION ==========
    app_name: str = "unknown-unknowns-agent"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # ========== DATABASE - POSTGRES ==========
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "igniten_core"
    postgres_user: str = "igniten_user"
    postgres_password: str = ""
    postgres_pool_min_size: int = 5
    postgres_pool_max_size: int = 20

    @property
    def database_url(self) -> str:
        """Construye connection string de Postgres"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ========== DATABASE - NEO4J ==========
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # ========== DATABASE - CHROMADB ==========
    chromadb_host: str = "localhost"
    chromadb_port: int = 8000
    chromadb_path: Optional[str] = None
    enable_chromadb: bool = True

    # ========== DATABASE - REDIS ==========
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    @property
    def redis_url(self) -> str:
        """Construye Redis URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ========== LLM - GEMINI ==========
    google_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash-latest"
    gemini_temperature: float = 0.7
    gemini_max_tokens: int = 2048

    # ========== EMBEDDINGS ==========
    openai_api_key: Optional[str] = None
    use_google_embeddings: bool = True
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # ========== API CONFIGURATION ==========
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_reload: bool = True
    cors_origins: str = "http://localhost:3000,http://localhost:8080"
    cors_allow_credentials: bool = True

    @property
    def cors_origins_list(self) -> List[str]:
        """Convierte CORS origins string a lista"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # ========== UNKNOWN UNKNOWNS CONFIGURATION ==========
    default_max_hypotheses: int = 20
    default_max_insights_to_deliver: int = 5
    default_min_insight_priority: int = 3
    default_min_impact_usd: int = 10000

    # ========== DELIVERY CHANNELS ==========
    enable_email_delivery: bool = False
    enable_teams_delivery: bool = False
    enable_whatsapp_delivery: bool = False
    enable_slack_delivery: bool = False

    # Email config
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: str = "noreply@igniten.ai"

    # Teams config
    teams_webhook_url: Optional[str] = None

    # WhatsApp config
    whatsapp_api_token: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None

    # Slack config
    slack_bot_token: Optional[str] = None
    slack_channel_id: Optional[str] = None

    # ========== SCHEDULED RUNS ==========
    enable_scheduled_runs: bool = False
    daily_run_enabled: bool = False
    daily_run_time: str = "08:00"
    weekly_run_enabled: bool = False
    weekly_run_day: str = "monday"
    weekly_run_time: str = "09:00"
    monthly_run_enabled: bool = False
    monthly_run_day: int = 1
    monthly_run_time: str = "10:00"

    # ========== MONITORING ==========
    sentry_dsn: Optional[str] = None
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 0.1
    log_file_path: str = "/var/log/igniten/unknown-unknowns.log"

    # ========== SECURITY ==========
    api_secret_key: str = "change-this-in-production"
    api_access_token_expire_minutes: int = 60

    # ========== FEATURE FLAGS ==========
    enable_profile_enrichment: bool = False
    enable_conversation_learning: bool = False
    enable_schema_analysis: bool = False

    # ========== PERFORMANCE ==========
    sql_query_timeout: int = 30
    max_parallel_validations: int = 5
    profile_cache_ttl: int = 3600
    insights_cache_ttl: int = 300

    # ========== DEVELOPMENT ==========
    auto_reload: bool = True
    mock_llm: bool = False
    mock_email: bool = False
    mock_databases: bool = False

    # ========== AGENT CLIENT ==========
    # URL del contenedor 'agent' en igniten_network_global
    agent_base_url: str = "http://agent:8000"
    # user_id enviado en cada request al agente
    agent_user_id: str = "unknown-unknowns-agent"
    # Timeout en segundos por request (el agente puede tardar en analizar)
    agent_timeout_seconds: int = 120
    # Reintentos ante errores temporales (429, 502, 503, timeouts)
    agent_max_retries: int = 3
    # Segundos base entre reintentos (escala exponencialmente: 5s, 10s, 20s)
    agent_retry_delay_seconds: float = 5.0

    # ========== CRON SCHEDULER ==========
    # Timezone para el scheduler (Colombia = UTC-5)
    cron_timezone: str = "America/Bogota"
    # Día de la semana para el run semanal
    cron_day_of_week: str = "thursday"
    # Hora del run (hora local según cron_timezone)
    cron_hour: int = 11
    # Minuto del run
    cron_minute: int = 0

    # ========== PIPELINE CONFIGURATION ==========
    # Máximo total de hipótesis por cliente por run
    max_hypotheses_per_client: int = 10
    # Hipótesis generadas desde known_pain_points
    max_pain_point_hypotheses: int = 5
    # Hipótesis generadas desde strategic_priorities
    max_priority_hypotheses: int = 5
    # Tipo de run a registrar en unknown_unknowns_runs
    pipeline_run_type: str = "weekly"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Obtiene settings (cached).
    Usar esta función en lugar de instanciar Settings() directamente.
    """
    return Settings()
