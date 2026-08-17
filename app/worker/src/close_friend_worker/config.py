import os

OLLAMA_BASE_URL = os.environ.get("CF_WORKER_OLLAMA_BASE_URL", "http://localhost:11434")
REDIS_URL = os.environ.get("CF_WORKER_REDIS_URL", "redis://localhost:6379/0")
CHAT_MODEL = os.environ.get("CF_WORKER_CHAT_MODEL", "qwen2.5:7b-instruct-q4_K_M")
