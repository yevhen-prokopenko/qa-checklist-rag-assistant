"""Central config loaded from .env."""
import os
from dotenv import load_dotenv

load_dotenv()

# Embeddings
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = 1536  # text-embedding-3-small=1536, -3-large=3072. Keep in sync with DB schema.

# Generation
GEN_PROVIDER = os.getenv("GEN_PROVIDER", "openai")
GEN_MODEL = os.getenv("GEN_MODEL", "gpt-4o-mini")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Postgres
PG = dict(
    host=os.getenv("PG_HOST", "localhost"),
    port=int(os.getenv("PG_PORT", "5434")),
    dbname=os.getenv("PG_DB", "ragdemo"),
    user=os.getenv("PG_USER", "rag"),
    password=os.getenv("PG_PASSWORD", "ragpass"),
)

# Jira
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")

# Retrieval params
TOP_K = 5          # final examples fed to LLM
RETRIEVE_N = 20    # candidates before optional rerank/hybrid
MAX_PER_SOURCE = 2 # diversification: max chunks from the same source_key in final TOP_K
