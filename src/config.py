import os

ROLE_NAMES = ("ARCHITECT", "PLANNER", "WRITER", "CRITIC", "SCANNER")

def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default

def _env_int(name: str, default: int) -> int:
    raw = _env_str(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default

def _env_float(name: str, default: float) -> float:
    raw = _env_str(name, str(default))
    try:
        return float(raw)
    except ValueError:
        return default


# =============================
# Generation Model Configuration
# =============================
# Options: "gemini", "openai"
PRIMARY_MODEL_TYPE = _env_str("PRIMARY_MODEL_TYPE", "openai")
ROLE_MODEL_TYPES = {
    role: _env_str(f"{role}_MODEL_TYPE", PRIMARY_MODEL_TYPE) for role in ROLE_NAMES
}
ARCHITECT_MODEL_TYPE = ROLE_MODEL_TYPES["ARCHITECT"]
PLANNER_MODEL_TYPE = ROLE_MODEL_TYPES["PLANNER"]
WRITER_MODEL_TYPE = ROLE_MODEL_TYPES["WRITER"]
CRITIC_MODEL_TYPE = ROLE_MODEL_TYPES["CRITIC"]
SCANNER_MODEL_TYPE = ROLE_MODEL_TYPES["SCANNER"]

# Gemini settings (generation)
GEMINI_API_KEY = _env_str("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
GEMINI_MODEL_NAME = _env_str("GEMINI_MODEL_NAME", "gemini-3-flash")
ROLE_GEMINI_MODEL_NAMES = {
    role: _env_str(f"{role}_GEMINI_MODEL_NAME", GEMINI_MODEL_NAME) for role in ROLE_NAMES
}
ARCHITECT_GEMINI_MODEL_NAME = ROLE_GEMINI_MODEL_NAMES["ARCHITECT"]
PLANNER_GEMINI_MODEL_NAME = ROLE_GEMINI_MODEL_NAMES["PLANNER"]
WRITER_GEMINI_MODEL_NAME = ROLE_GEMINI_MODEL_NAMES["WRITER"]
CRITIC_GEMINI_MODEL_NAME = ROLE_GEMINI_MODEL_NAMES["CRITIC"]
SCANNER_GEMINI_MODEL_NAME = ROLE_GEMINI_MODEL_NAMES["SCANNER"]

# OpenAI-compatible settings (generation), e.g. LM Studio / llama.cpp / vLLM
OPENAI_API_KEY = _env_str("OPENAI_API_KEY", "lm-studio")
OPENAI_BASE_URL = _env_str("OPENAI_BASE_URL", "http://localhost:----/v1")
OPENAI_MODEL_NAME = _env_str("OPENAI_MODEL_NAME", "local-model")
ROLE_OPENAI_MODEL_NAMES = {
    role: _env_str(f"{role}_OPENAI_MODEL_NAME", OPENAI_MODEL_NAME) for role in ROLE_NAMES
}
ARCHITECT_OPENAI_MODEL_NAME = ROLE_OPENAI_MODEL_NAMES["ARCHITECT"]
PLANNER_OPENAI_MODEL_NAME = ROLE_OPENAI_MODEL_NAMES["PLANNER"]
WRITER_OPENAI_MODEL_NAME = ROLE_OPENAI_MODEL_NAMES["WRITER"]
CRITIC_OPENAI_MODEL_NAME = ROLE_OPENAI_MODEL_NAMES["CRITIC"]
SCANNER_OPENAI_MODEL_NAME = ROLE_OPENAI_MODEL_NAMES["SCANNER"]

# =============================
# Embedding Configuration
# =============================
# Options: "gemini", "openai"
EMBEDDING_PROVIDER = _env_str("EMBEDDING_PROVIDER", "openai")
EMBEDDING_BASE_URL = _env_str("EMBEDDING_BASE_URL", "http://localhost:----/v1")
EMBEDDING_API_KEY = _env_str("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL_NAME = _env_str("EMBEDDING_MODEL_NAME", "local-embedding-model")
EMBEDDING_DIM = _env_int("EMBEDDING_DIM", 768)
GEMINI_EMBEDDING_MODEL = _env_str("GEMINI_EMBEDDING_MODEL", "text-embedding-004")

# =============================
# Paths / Project
# =============================
DB_PATH = _env_str("DB_PATH", "novel/process/facts/facts.db")
FAISS_INDEX_PATH = _env_str("FAISS_INDEX_PATH", "novel/process/facts/vector_index.faiss")
NOVEL_TITLE = _env_str("NOVEL_TITLE", "Untitled Novel")
OUTPUT_DIR = _env_str("OUTPUT_DIR", "novel/main_text")
FRAME_DIR = _env_str("FRAME_DIR", "novel/frame")
PROCESS_DIR = _env_str("PROCESS_DIR", "novel/process")
LANGUAGE = _env_str("LANGUAGE", "English")  # "English" or "Chinese"

# =============================
# Retrieval / Constraint Controls
# =============================
TIER_1_RELEVANCE_THRESHOLD = _env_float("TIER_1_RELEVANCE_THRESHOLD", 0.9)
TIER_3_SEARCH_LIMIT = _env_int("TIER_3_SEARCH_LIMIT", 5)

# =============================
# Workflow Controls
# =============================
WORLD_DISCUSSION_ROUNDS = _env_int("WORLD_DISCUSSION_ROUNDS", 1)
PLOT_DISCUSSION_ROUNDS = _env_int("PLOT_DISCUSSION_ROUNDS", 1)
DETAILED_PLOT_DISCUSSION_ROUNDS = _env_int("DETAILED_PLOT_DISCUSSION_ROUNDS", 1)
CHAPTER_GUIDE_DISCUSSION_ROUNDS = _env_int("CHAPTER_GUIDE_DISCUSSION_ROUNDS", 1)
CHAPTER_REVISION_ROUNDS = _env_int("CHAPTER_REVISION_ROUNDS", 1)
CHAPTER_TEXT_DISCUSSION_ROUNDS = _env_int(
    "CHAPTER_TEXT_DISCUSSION_ROUNDS", CHAPTER_REVISION_ROUNDS
)
AUTO_GENERATION_MAX_RETRIES = _env_int("AUTO_GENERATION_MAX_RETRIES", 3)

# Blocking conflict governance mode:
# - "auto_keep_existing": auto-resolve BLOCKING conflicts by keep_existing before gating.
# - "manual_block": never auto-resolve BLOCKING conflicts; fail fast until resolved manually.
BLOCKING_CONFLICT_MODE = _env_str("BLOCKING_CONFLICT_MODE", "auto_keep_existing").lower()
