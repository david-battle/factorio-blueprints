"""Small atomic flat-text state files for the full Jimbo bot."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Mapping

from .archive import escape_field, unescape_field


STATE_MAGIC = "JIMBO_STATE"
STATE_VERSION = 1
STATE_NAMES = frozenset(
    {
        "cursor",
        "seen_players",
        "preferences",
        "deliveries",
        "runtime_flags",
        "placement_runs",
        "placement_batches",
    }
)
SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


class StateError(RuntimeError):
    """Raised when a state file is invalid or unsupported."""


class FlatTextStateStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def load(self, name: str) -> dict[str, str]:
        path = self._path(name)
        if not path.exists():
            return {}
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        if not lines:
            raise StateError(f"state file is empty: {name}")
        header = lines[0].split("\t")
        if len(header) != 3 or header[0] != STATE_MAGIC or header[2] != name:
            if all("=" in line for line in lines if line):
                return self._migrate_version_zero(name, path, lines)
            raise StateError(f"state header is invalid: {name}")
        try:
            version = int(header[1])
        except ValueError as error:
            raise StateError(f"state version is invalid: {name}") from error
        if version != STATE_VERSION:
            raise StateError(f"unsupported state version {version}: {name}")
        result: dict[str, str] = {}
        for line_number, line in enumerate(lines[1:], start=2):
            fields = line.split("\t")
            if len(fields) != 2:
                raise StateError(f"invalid state record {name}:{line_number}")
            try:
                key, value = (unescape_field(field) for field in fields)
            except ValueError as error:
                raise StateError(f"invalid state escape {name}:{line_number}") from error
            self._validate_key(key)
            if key in result:
                raise StateError(f"duplicate state key {key}: {name}")
            result[key] = value
        return result

    def replace(self, name: str, values: Mapping[str, str]) -> None:
        path = self._path(name)
        lines = [f"{STATE_MAGIC}\t{STATE_VERSION}\t{name}\n"]
        for key in sorted(values):
            self._validate_key(key)
            value = values[key]
            if not isinstance(value, str):
                raise StateError(f"state value must be text: {key}")
            lines.append(f"{escape_field(key)}\t{escape_field(value)}\n")
        self._atomic_replace(path, "".join(lines))

    def integrity_check(self) -> tuple[str, ...]:
        issues: list[str] = []
        for name in sorted(STATE_NAMES):
            try:
                self.load(name)
            except (OSError, UnicodeError, StateError) as error:
                issues.append(f"{name}: {error}")
        return tuple(issues)

    def _migrate_version_zero(
        self, name: str, path: Path, lines: list[str]
    ) -> dict[str, str]:
        values: dict[str, str] = {}
        for line_number, line in enumerate(lines, start=1):
            if not line:
                continue
            key, separator, value = line.partition("=")
            if not separator:
                raise StateError(f"invalid legacy state record {name}:{line_number}")
            self._validate_key(key)
            values[key] = value
        backup = path.with_suffix(path.suffix + ".v0.bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        self.replace(name, values)
        return values

    def _path(self, name: str) -> Path:
        if name not in STATE_NAMES:
            raise StateError(f"unknown state file: {name}")
        return self.directory / f"{name}.state"

    @staticmethod
    def _validate_key(key: str) -> None:
        if not SAFE_KEY_RE.fullmatch(key):
            raise StateError(f"invalid state key: {key!r}")

    @staticmethod
    def _atomic_replace(path: Path, contents: str) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
