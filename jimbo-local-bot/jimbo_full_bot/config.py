"""Validated, secret-safe configuration for the full Jimbo bot."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
DEFAULT_SERVER_LOG = Path(r"D:\factorio-server\server-console.log")
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime"
DEFAULT_GROQ_KEY = DEFAULT_RUNTIME_DIR / "groq-api-key.txt"
DEFAULT_RCON_WRAPPER = REPOSITORY_ROOT / "tools" / "factorio-rcon.ps1"
DEFAULT_RCON_COMMAND = REPOSITORY_ROOT / "tools" / "rcon-command.txt"


class ConfigurationError(ValueError):
    """Raised when full-bot configuration is internally inconsistent."""


@dataclass(frozen=True, slots=True)
class FullBotConfig:
    """All Step 1 configuration; construction performs no filesystem I/O."""

    provider: str = "groq"
    model: str = "openai/gpt-oss-120b"
    management_player: str = "dlbattle"
    server_philosophy: str = (
        "Give players as much freedom as possible without breaking the game. "
        "Humans decide what behavior is acceptable, not scripts, bots, or AI models."
    )
    moderator_roster: tuple[str, ...] = ()
    server_log_path: Path = DEFAULT_SERVER_LOG
    runtime_dir: Path = DEFAULT_RUNTIME_DIR
    api_key_path: Path = DEFAULT_GROQ_KEY
    rcon_wrapper_path: Path = DEFAULT_RCON_WRAPPER
    rcon_command_path: Path = DEFAULT_RCON_COMMAND
    provider_timeout_seconds: float = 60.0
    rcon_timeout_seconds: float = 15.0
    poll_interval_seconds: float = 0.25
    chat_character_limit: int = 220
    queue_limit: int = 5
    public_replies_enabled: bool = False
    welcomes_enabled: bool = False
    live_log_enabled: bool = False
    live_rcon_enabled: bool = False
    placement_enabled: bool = False
    archive_rotation_bytes: int = 10_000_000

    def validate(self) -> FullBotConfig:
        if self.provider.casefold() != "groq":
            raise ConfigurationError("provider must be 'groq' for the first release")
        if not self.model.strip():
            raise ConfigurationError("model cannot be empty")
        if not self.management_player.strip():
            raise ConfigurationError("management_player cannot be empty")
        if self.management_player != self.management_player.strip():
            raise ConfigurationError("management_player cannot have outer whitespace")
        if not self.server_philosophy.strip():
            raise ConfigurationError("server_philosophy cannot be empty")
        if not isinstance(self.moderator_roster, tuple) or not all(
            isinstance(name, str) and name.strip() for name in self.moderator_roster
        ):
            raise ConfigurationError("moderator_roster must contain non-empty names")
        for name in (
            "server_log_path",
            "runtime_dir",
            "api_key_path",
            "rcon_wrapper_path",
            "rcon_command_path",
        ):
            value = getattr(self, name)
            if not isinstance(value, Path) or not str(value):
                raise ConfigurationError(f"{name} must be a non-empty Path")
        for name in (
            "provider_timeout_seconds",
            "rcon_timeout_seconds",
            "poll_interval_seconds",
        ):
            if getattr(self, name) <= 0:
                raise ConfigurationError(f"{name} must be greater than zero")
        if not 40 <= self.chat_character_limit <= 1000:
            raise ConfigurationError("chat_character_limit must be between 40 and 1000")
        if not 1 <= self.queue_limit <= 100:
            raise ConfigurationError("queue_limit must be between 1 and 100")
        if self.archive_rotation_bytes < 1024:
            raise ConfigurationError("archive_rotation_bytes must be at least 1024")
        if self.placement_enabled and not self.live_rcon_enabled:
            raise ConfigurationError("placement requires live_rcon_enabled")
        if self.public_replies_enabled and not self.live_rcon_enabled:
            raise ConfigurationError("public replies require live_rcon_enabled")
        if self.welcomes_enabled and not self.public_replies_enabled:
            raise ConfigurationError("welcomes require public_replies_enabled")
        return self

    @classmethod
    def offline(cls) -> FullBotConfig:
        """Return the validated Step 1 configuration without reading any path."""
        return cls().validate()

    def with_overrides(self, **changes: Any) -> FullBotConfig:
        known = {field.name for field in fields(self)}
        unknown = sorted(set(changes) - known)
        if unknown:
            raise ConfigurationError(f"unknown configuration field: {unknown[0]}")
        return replace(self, **changes).validate()

    def safe_summary(self) -> tuple[tuple[str, str], ...]:
        """Return an allowlisted diagnostic summary with no secret contents."""
        return (
            ("mode", "offline" if not self.live_log_enabled else "live-log"),
            ("provider", self.provider),
            ("model", self.model),
            ("management_player", self.management_player),
            ("api_key", "configured path (not read)"),
            ("public_replies", _on_off(self.public_replies_enabled)),
            ("welcomes", _on_off(self.welcomes_enabled)),
            ("live_log", _on_off(self.live_log_enabled)),
            ("live_rcon", _on_off(self.live_rcon_enabled)),
            ("placement", _on_off(self.placement_enabled)),
            ("queue_limit", str(self.queue_limit)),
            ("chat_character_limit", str(self.chat_character_limit)),
        )


def _on_off(value: bool) -> str:
    return "enabled" if value else "disabled"
