import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    EBI_BASE_URL: str = "https://www.ebi.ac.uk/Tools/services/rest/ncbiblast"
    UNIPROT_BASE_URL: str = "https://rest.uniprot.org/uniprotkb"
    ALPHAFOLD_DB_URL: str = "https://alphafold.ebi.ac.uk/api/prediction"
    DAILY_LIMIT: int = 10
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "groq/llama-3.3-70b-versatile")
    PRO_MODEL: str = os.getenv("PRO_MODEL", "claude-sonnet-4-20250514")


settings = Settings()
