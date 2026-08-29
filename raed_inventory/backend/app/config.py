import os
import secrets
import warnings

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = os.getenv("ENV_FILE", ".env")

# قيمة الـ fallback المعروفة (لا يجب أن تُستخدم في production)
_INSECURE_DEFAULT_SECRET = "raed-super-secret-key-change-in-production-2025"  # noqa: S105
_INSECURE_DEFAULT_ADMIN_PW = "Admin@2025"  # noqa: S105


class Settings(BaseSettings):
    # ─── Database ────────────────────────────────────────────────────────────
    # في local يشتغل SQLite تلقائياً — في production حط DATABASE_URL في .env
    DATABASE_URL: str = "sqlite:///./raed_inventory_local.db"

    # ─── JWT ─────────────────────────────────────────────────────────────────
    # ⚠️  SECRET_KEY لازم يكون من env var في production
    # القيمة الافتراضية تُستبدل تلقائياً بقيمة عشوائية إذا كانت هي الـ fallback
    # المعروفة (راجع post-init أدناه)
    SECRET_KEY: str = _INSECURE_DEFAULT_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ─── App ─────────────────────────────────────────────────────────────────
    APP_NAME: str = "Raed Inventory System"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "local"          # local | staging | production
    DEBUG: bool = False                 # افتراضياً off — فعّل بـ env var DEBUG=true

    # ─── Timezone ────────────────────────────────────────────────────────────
    DEFAULT_TIMEZONE: str = "Asia/Riyadh"  # AST (UTC+3) — مهم لحدود اليوم التجاري

    # ─── CORS ────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = (
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"
    )

    # ─── Rate Limiting ───────────────────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "200/minute"
    RATE_LIMIT_AUTH: str = "20/minute"

    # ─── AI Assistant ────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""                # يُحقَن عبر env var على Railway
    OPENAI_MODEL: str = "gpt-4o-mini"       # نموذج اقتصادي و سريع للـ MVP
    ASSISTANT_ENABLED: bool = True          # يقدر admin يطفّيه من env vars
    ASSISTANT_MAX_TOKENS: int = 800
    ASSISTANT_TEMPERATURE: float = 0.3      # قليل عشان ميختلقش حاجات

    # ─── Features ────────────────────────────────────────────────────────────
    AUDIT_LOG_ENABLED: bool = True
    DEFAULT_TENANT_ID: int = 1
    MULTI_TENANT_ENABLED: bool = False
    IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS: int = 3600
    IDEMPOTENCY_TTL_SECONDS: int = 86400

    # ─── Replenishment Scheduler ─────────────────────────────────────────────
    REPLENISHMENT_SCHEDULER_ENABLED: bool = False
    REPLENISHMENT_SCHEDULE_HOUR: int = 6   # الساعة 6 صباحاً بتوقيت السعودية
    REPLENISHMENT_SCHEDULE_MINUTE: int = 0

    # ─── Shift Operations ────────────────────────────────────────────────────
    CASH_VARIANCE_TOLERANCE: float = 5.0
    # Shift cash screen deferred by owner 2026-08-18, not removed. While False, a shift
    # completes on count submit alone. Re-enable via env without code changes.
    SHIFT_CASH_ENABLED: bool = False

    # ─── File Upload Limits ──────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 20  # 20 MB كحد أقصى لأي ملف مرفوع

    # ─── Upload Paths ────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    QUALITY_UPLOAD_DIR: str = "./uploads/quality"
    DOCUMENTS_UPLOAD_DIR: str = "./uploads/documents"

    # ─── Seed Admin ──────────────────────────────────────────────────────────
    # تُستخدم فقط عند seed.py — غيّرها في .env
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "admin@raed.com"
    ADMIN_PASSWORD: str = _INSECURE_DEFAULT_ADMIN_PW

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_staging(self) -> bool:
        return self.ENVIRONMENT.lower() == "staging"

    @property
    def is_deployment_env(self) -> bool:
        return self.is_production or self.is_staging

    def validate_security(self) -> None:
        """
        يرفع خطأ صريح لو secret ضعيف في production.
        في local: يُحذّر فقط.
        """
        if self.SECRET_KEY == _INSECURE_DEFAULT_SECRET:
            if self.is_production:
                raise RuntimeError(
                    "SECRET_KEY هو القيمة الافتراضية غير الآمنة. "
                    "عيِّن متغير البيئة SECRET_KEY قبل تشغيل الـ production."
                )
            # local/staging: نولّد قيمة عشوائية في الذاكرة (لا تُكتب)
            warnings.warn(
                "⚠️  SECRET_KEY الافتراضي مُستخدم. تم توليد قيمة عشوائية مؤقتة. "
                "حدِّد SECRET_KEY في ملف .env للاستمرارية.",
                stacklevel=2,
            )
            # Mutate in-memory (won't be persisted; each restart yields a new one in local dev)
            object.__setattr__(self, "SECRET_KEY", secrets.token_urlsafe(48))

        if self.is_deployment_env and self.DEBUG:
            raise RuntimeError("DEBUG=True ممنوع في staging/production. عيِّن DEBUG=false.")

        if self.is_deployment_env and self.ADMIN_PASSWORD == _INSECURE_DEFAULT_ADMIN_PW:
            raise RuntimeError(
                "ADMIN_PASSWORD هو القيمة الافتراضية. عيِّن قيمة قوية في .env قبل staging/production."
            )

        if self.is_deployment_env and self.DATABASE_URL.lower().startswith("sqlite"):
            raise RuntimeError(
                "SQLite is not allowed in staging/production. Configure DATABASE_URL to PostgreSQL before startup."
            )

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")


settings = Settings()
settings.validate_security()
