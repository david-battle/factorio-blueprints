"""Direct TCP RCON transport replacing the PowerShell+exe subprocess chain.

Uses the mcrcon library for pure-Python Source RCON protocol support.
Eliminates the rcon-command.txt temp-file race condition and the
PowerShell startup overhead on every RCON interaction.
"""

from __future__ import annotations

import math
from pathlib import Path

from mcrcon import MCRcon


class RconTransportError(RuntimeError):
    """Raised when the direct RCON transport cannot complete an operation."""


class DirectRconTransport:
    """Synchronous RCON transport over TCP using mcrcon."""

    def __init__(self, host: str, port: int, password: str, timeout: float = 15.0) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout

    def command(self, cmd: str, *, timeout: float | None = None) -> str:
        """Connect, authenticate, execute one command, and disconnect.

        Each call opens and closes a fresh TCP session. This is slightly slower
        than a persistent connection but eliminates lifecycle management and
        matches the existing one-shot-per-request pattern used by all providers.
        """
        effective_timeout = timeout if timeout is not None else self.timeout
        # mcrcon passes this value to signal.alarm(), which only accepts integers.
        alarm_timeout = max(1, math.ceil(effective_timeout))
        try:
            client = MCRcon(self.host, self.password, port=self.port, timeout=alarm_timeout)
            client.connect()
            try:
                return client.command(cmd)
            finally:
                client.disconnect()
        except Exception as exc:
            raise RconTransportError(f"RCON command failed: {exc}") from exc

    @classmethod
    def from_password_file(
        cls,
        password_file: str | Path,
        host: str = "127.0.0.1",
        port: int = 27015,
        timeout: float = 15.0,
    ) -> DirectRconTransport:
        path = Path(password_file)
        if not path.exists():
            raise RconTransportError(f"RCON password file not found: {path}")
        password = path.read_text(encoding="utf-8").strip()
        if not password:
            raise RconTransportError(f"RCON password file is empty: {path}")
        return cls(host, port, password, timeout)
