"""Standalone Factorio RCON client (Linux-native, pure Python).

Wraps the mcrcon library for direct TCP RCON access without PowerShell or
external executables. Can be used as a library, a CLI tool, or a drop-in
replacement for the PowerShell+exe chain.

Usage as CLI:
    python rcon_client.py --password-file /path/to/rconpw
    python rcon_client.py --password-file /path/to/rconpw --command '/players'
    python rcon_client.py --password-file /path/to/rconpw --interactive
    echo '/players' | python rcon_client.py --password-file /path/to/rconpw

Usage as library:
    from rcon_client import RconClient
    with RconClient.from_password_file("/path/to/rconpw") as client:
        output = client.command("/players")
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mcrcon import MCRcon


class RconError(RuntimeError):
    """Raised on RCON connection or authentication errors."""


class RconClient:
    """Simple synchronous RCON client wrapping mcrcon."""

    def __init__(self, host: str, port: int, password: str, timeout: float = 15.0) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._mcrcon: MCRcon | None = None

    def connect(self) -> None:
        """Open TCP connection and authenticate."""
        if self._mcrcon is not None:
            return
        try:
            self._mcrcon = MCRcon(self.host, self.password, port=self.port, timeout=self.timeout)
            self._mcrcon.connect()
        except Exception as exc:
            self._mcrcon = None
            raise RconError(f"cannot connect to {self.host}:{self.port}: {exc}") from exc

    def close(self) -> None:
        """Disconnect."""
        if self._mcrcon is not None:
            try:
                self._mcrcon.disconnect()
            except Exception:
                pass
            self._mcrcon = None

    @property
    def connected(self) -> bool:
        return self._mcrcon is not None

    def command(self, cmd: str, *, timeout: float | None = None) -> str:
        """Send an RCON command and return the response body."""
        if self._mcrcon is None:
            raise RconError("not connected; call connect() first")
        try:
            if timeout is not None:
                self._mcrcon.timeout = timeout
            return self._mcrcon.command(cmd)
        except Exception as exc:
            raise RconError(f"RCON command failed: {exc}") from exc

    def __enter__(self) -> RconClient:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @classmethod
    def from_password_file(
        cls,
        password_file: str | Path,
        host: str = "127.0.0.1",
        port: int = 27015,
        timeout: float = 15.0,
    ) -> RconClient:
        """Create a client from a password file path."""
        path = Path(password_file)
        if not path.exists():
            raise RconError(f"password file not found: {path}")
        password = path.read_text(encoding="utf-8").strip()
        return cls(host, port, password, timeout)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Standalone Factorio RCON client (Linux-native, pure Python)."
    )
    parser.add_argument("--host", default="127.0.0.1", help="RCON host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=27015, help="RCON port (default: 27015)")
    parser.add_argument(
        "--password-file",
        default=None,
        help="Path to file containing the RCON password",
    )
    parser.add_argument(
        "--command", "-c", default=None,
        help="Single command to execute; if omitted, reads from stdin",
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Interactive mode: prompt for commands until EOF/quit",
    )
    parser.add_argument(
        "--timeout", type=float, default=15.0,
        help="Socket timeout in seconds (default: 15)",
    )
    args = parser.parse_args()

    if args.password_file is None:
        parser.error("--password-file is required")

    client = RconClient.from_password_file(
        args.password_file, host=args.host, port=args.port, timeout=args.timeout,
    )
    try:
        client.connect()
    except RconError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.interactive:
        _run_interactive(client)
    elif args.command is not None:
        _run_single(client, args.command)
    else:
        _run_stdin(client)

    client.close()


def _run_single(client: RconClient, cmd: str) -> None:
    try:
        output = client.command(cmd)
        if output:
            print(output)
    except RconError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


def _run_stdin(client: RconClient) -> None:
    for line in sys.stdin:
        cmd = line.strip()
        if not cmd:
            continue
        try:
            output = client.command(cmd)
            if output:
                print(output)
        except RconError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)


def _run_interactive(client: RconClient) -> None:
    print(f"Connected to {client.host}:{client.port}. Type commands or 'quit'.")
    try:
        while True:
            try:
                cmd = input("rcon> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if cmd.lower() in ("quit", "exit", "q"):
                break
            if not cmd:
                continue
            try:
                output = client.command(cmd)
                if output:
                    print(output)
            except RconError as exc:
                print(f"Error: {exc}", file=sys.stderr)
    finally:
        client.close()


if __name__ == "__main__":
    main()
