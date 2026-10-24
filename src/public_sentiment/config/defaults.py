from ..core.constants import APP_NAMES

DEFAULT_CONFIG = {
    "system": {"name": "观潮 · 舆情分析平台", "auto_start": False, "max_results": 100, "request_timeout": 15},
    "collection": {"mode": "database", "rss_feeds": [], "internal_file": "", "forum_interval": 15},
    "database": {
        "driver": "mysql", "name": "media_crawler", "host_env": "MEDIA_CRAWLER_DB_HOST",
        "port_env": "MEDIA_CRAWLER_DB_PORT", "user_env": "MEDIA_CRAWLER_DB_USER",
        "password_env": "MEDIA_CRAWLER_DB_PASSWORD", "timezone": "+08:00", "ssl_ca": "", "tables": [],
    },
    "llm": {
        "base_url": "http://127.0.0.1:8001/v1", "model": "",
        "api_key_env": "LLM_API_KEY", "base_url_env": "LLM_BASE_URL", "model_env": "LLM_MODEL",
        "response_format": "json_object", "temperature": 0.2, "max_tokens": 6000,
        "timeout": 120, "max_retries": 1, "batch_size": 5, "max_chars_per_source": 6000,
        "capture_training": True,
    },
    "apps": {name: True for name in APP_NAMES},
}
