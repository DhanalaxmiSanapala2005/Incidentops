import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'incidentops.db'}")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me-dev-secret-change-me")
    TOKEN_TTL_MIN = int(os.getenv("TOKEN_TTL_MIN", "480"))
    SERVICE_KEY = os.getenv("MOCK_SERVICE_KEY", "mock-monitoring-key")
    MOCK_BASE_URL = os.getenv("MOCK_BASE_URL", "http://localhost:8001")
    MOCK_TIMEOUT_S = float(os.getenv("MOCK_TIMEOUT_S", "5"))
    RETRY_BACKOFF_S = float(os.getenv("RETRY_BACKOFF_S", "0.05"))
    # LLM: none | anthropic | ollama. "none" => deterministic template narrative (always safe fallback).
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
    LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "20"))
    LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
    COST_IN_PER_MTOK = float(os.getenv("COST_IN_PER_MTOK", "3"))
    COST_OUT_PER_MTOK = float(os.getenv("COST_OUT_PER_MTOK", "15"))
    EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "ollama" if os.getenv("LLM_PROVIDER", "none").lower() == "ollama" else "none").lower()
    EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
    EMBED_TIMEOUT_S = float(os.getenv("EMBED_TIMEOUT_S", "30"))
    RAG_MIN_DENSE = float(os.getenv("RAG_MIN_DENSE", "0"))  # 0 = never abstain on similarity alone (unmeasured; see docs/rag_eval)
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(ROOT / "data" / "uploads")))
    DEFAULT_APPROVAL_TTL_MIN = 30
    CORRELATION_WINDOW_MIN = 30


settings = Settings()
