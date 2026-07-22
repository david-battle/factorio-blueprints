"""Minimal model-authored RCON execution path for Step 10."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .contracts import Provenance, ResultStatus, ToolResult
from .delivery import POWERSHELL_PATH


MAX_CAPTURE_CHARS = 200_000


class FreeformRconError(RuntimeError):
    """Raised when a generated RCON command cannot be executed observably."""


class FreeformRconProvider:
    def __init__(self, *, wrapper_path: Path, command_path: Path, timeout_seconds: float) -> None:
        self.wrapper_path = wrapper_path
        self.command_path = command_path
        self.timeout_seconds = timeout_seconds

    def execute(self, command: str) -> ToolResult:
        original = self.command_path.read_bytes()
        try:
            self.command_path.write_text(command + "\n", encoding="utf-8")
            completed = subprocess.run(
                [str(POWERSHELL_PATH), "-NoProfile", "-File", str(self.wrapper_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise FreeformRconError(f"free-form RCON failed: {error}") from error
        finally:
            self.command_path.write_bytes(original)
        output = (completed.stdout + "\n" + completed.stderr).strip()
        if completed.returncode != 0:
            raise FreeformRconError(
                f"free-form RCON exited {completed.returncode}: {output[:1000]}"
            )
        truncated = len(output) > MAX_CAPTURE_CHARS
        captured = output[:MAX_CAPTURE_CHARS]
        return ToolResult(
            ResultStatus.PARTIAL if truncated else ResultStatus.COMPLETE,
            "Free-form RCON returned output" + (" (truncated)." if truncated else "."),
            Provenance.now("model_authored_rcon", "server=current"),
            {"output": captured},
            ("RCON output exceeded capture limit",) if truncated else (),
        )
