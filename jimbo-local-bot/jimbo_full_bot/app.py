"""Offline Step 1 application shell."""

from __future__ import annotations

from dataclasses import dataclass

from .config import FullBotConfig


@dataclass(frozen=True, slots=True)
class StartupReport:
    name: str
    status: str
    summary: tuple[tuple[str, str], ...]

    def as_text(self) -> str:
        lines = [f"{self.name}: {self.status}"]
        lines.extend(f"{key}: {value}" for key, value in self.summary)
        return "\n".join(lines)


class FullBotApplication:
    """A side-effect-free shell until later plan steps wire dependencies."""

    def __init__(self, config: FullBotConfig) -> None:
        self.config = config.validate()

    @classmethod
    def offline(cls) -> FullBotApplication:
        return cls(FullBotConfig.offline())

    def startup_report(self) -> StartupReport:
        return StartupReport(
            name="Jimbo full bot",
            status="offline shell ready",
            summary=self.config.safe_summary(),
        )

    def run_offline(self) -> StartupReport:
        """Return status without opening configured paths or external clients."""
        return self.startup_report()
