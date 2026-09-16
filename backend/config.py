"""Utilitários de configuração e validação de chaves."""

import os

PLACEHOLDER_MARKERS = (
    "sua_chave",
    "seu_client",
    "seu_secret",
    "seu_usuario",
    "aqui",
    "your_",
    "example",
)


def is_valid_key(value: str | None) -> bool:
    """Retorna True se a variável tem valor real (não placeholder)."""
    if not value or not value.strip():
        return False
    lower = value.strip().lower()
    return not any(marker in lower for marker in PLACEHOLDER_MARKERS)


def get_config_status() -> dict[str, bool]:
    return {
        "groq": is_valid_key(os.getenv("GROQ_API_KEY")),
        "openai": is_valid_key(os.getenv("OPENAI_API_KEY")),
        "youtube": is_valid_key(os.getenv("YOUTUBE_API_KEY")),
        "reddit": is_valid_key(os.getenv("REDDIT_CLIENT_ID"))
        and is_valid_key(os.getenv("REDDIT_CLIENT_SECRET")),
    }
