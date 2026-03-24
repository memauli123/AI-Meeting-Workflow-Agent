"""
Config — Meeting Agent Pipeline
Central configuration loaded from environment variables and/or a config file.
All pipeline components import from here — never hardcode settings elsewhere.

Priority order (highest wins):
  1. Environment variables
  2. config.yml (if present)
  3. Defaults defined in this file
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field


# ── Helpers ───────────────────────────────────────────────────────────────────

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

def _env_int(key: str, default: int) -> int:
    val = os.environ.get(key)
    return int(val) if val is not None else default

def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key, "").lower()
    if val in ("1", "true", "yes"):
        return True
    if val in ("0", "false", "no"):
        return False
    return default

def _env_list(key: str, default: list) -> list:
    val = os.environ.get(key)
    if val:
        return [v.strip() for v in val.split(",")]
    return default


# ── Config dataclass ──────────────────────────────────────────────────────────

@dataclass
class PipelineConfig:
    # Anthropic
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    model: str = field(default_factory=lambda: _env("PIPELINE_MODEL", "claude-sonnet-4-20250514"))
    max_tokens: int = field(default_factory=lambda: _env_int("PIPELINE_MAX_TOKENS", 2000))

    # Pipeline behaviour
    validate_output: bool = field(default_factory=lambda: _env_bool("PIPELINE_VALIDATE", True))
    normalize_dates: bool = field(default_factory=lambda: _env_bool("PIPELINE_NORMALIZE_DATES", True))

    # Sensitivity defaults
    default_sensitivity: str = field(default_factory=lambda: _env("PIPELINE_DEFAULT_SENSITIVITY", "INTERNAL"))

    # Webhook
    webhook_enabled: bool = field(default_factory=lambda: _env_bool("WEBHOOK_ENABLED", False))
    webhook_url: str = field(default_factory=lambda: _env("WEBHOOK_URL", ""))
    webhook_secret: str = field(default_factory=lambda: _env("WEBHOOK_SECRET", ""))
    webhook_on_events: list = field(default_factory=lambda: _env_list(
        "WEBHOOK_ON_EVENTS", ["pipeline_complete", "high_risk_detected"]
    ))

    # API server
    api_host: str = field(default_factory=lambda: _env("API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: _env_int("API_PORT", 8000))
    api_reload: bool = field(default_factory=lambda: _env_bool("API_RELOAD", False))

    # Batch
    batch_max_workers: int = field(default_factory=lambda: _env_int("BATCH_MAX_WORKERS", 4))
    batch_output_dir: str = field(default_factory=lambda: _env("BATCH_OUTPUT_DIR", "outputs/batch"))

    # Exports
    export_dir: str = field(default_factory=lambda: _env("EXPORT_DIR", "outputs"))

    def validate(self) -> None:
        """Raise if required config is missing or invalid."""
        if not self.anthropic_api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file or export it as an environment variable."
            )
        valid_sensitivity = {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"}
        if self.default_sensitivity not in valid_sensitivity:
            raise ValueError(
                f"PIPELINE_DEFAULT_SENSITIVITY must be one of {valid_sensitivity}"
            )

    def to_dict(self) -> dict:
        """Return config as dict, with API key masked."""
        d = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "validate_output": self.validate_output,
            "normalize_dates": self.normalize_dates,
            "default_sensitivity": self.default_sensitivity,
            "webhook_enabled": self.webhook_enabled,
            "webhook_url": self.webhook_url,
            "webhook_on_events": self.webhook_on_events,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "batch_max_workers": self.batch_max_workers,
            "batch_output_dir": self.batch_output_dir,
            "export_dir": self.export_dir,
            "anthropic_api_key": "sk-ant-***" if self.anthropic_api_key else "(not set)",
        }
        return d


# ── Singleton ─────────────────────────────────────────────────────────────────

_config: PipelineConfig | None = None


def get_config() -> PipelineConfig:
    """Return the singleton config instance, loading it once."""
    global _config
    if _config is None:
        _load_dotenv()
        _config = PipelineConfig()
    return _config


def _load_dotenv() -> None:
    """Manually load .env file if present — no external dependency needed."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key not in os.environ:
                os.environ[key] = value


def reset_config() -> None:
    """Reset singleton — used in tests to force reload."""
    global _config
    _config = None
