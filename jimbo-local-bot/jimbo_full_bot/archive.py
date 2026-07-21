"""Simple append-only UTF-8 event archive for the full Jimbo bot."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


ARCHIVE_MAGIC = "JIMBO_EVENT"
ARCHIVE_VERSION = 1
ARCHIVE_FIELDS = 9
SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(?:groq[_-]?api[_-]?key|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"(?i)authorization\s*:\s*bearer\s+\S+"),
    re.compile(r"(?i)(?:rconpw|rcon[_-]?password)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(?:system|hidden)[_-]?prompt\s*[:=]\s*\S+"),
)


class ArchiveError(RuntimeError):
    """Base class for archive failures."""


class ArchivePrivacyError(ArchiveError):
    """Raised before secret-shaped content can be serialized."""


@dataclass(frozen=True, slots=True)
class ArchiveRecord:
    kind: str
    recorded_at: datetime
    payload: str
    event_id: str = ""
    correlation_id: str = ""
    actor: str = ""

    def __post_init__(self) -> None:
        if not self.kind or any(character.isspace() for character in self.kind):
            raise ValueError("archive kind must be a non-empty tag")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        for value in (self.kind, self.event_id, self.correlation_id, self.actor, self.payload):
            _reject_sensitive(value)

    @classmethod
    def now(
        cls,
        kind: str,
        payload: str,
        *,
        event_id: str = "",
        correlation_id: str = "",
        actor: str = "",
    ) -> ArchiveRecord:
        return cls(
            kind=kind,
            recorded_at=datetime.now(UTC),
            payload=payload,
            event_id=event_id,
            correlation_id=correlation_id,
            actor=actor,
        )


@dataclass(frozen=True, slots=True)
class ArchiveIssue:
    path: Path
    line_number: int
    reason: str


@dataclass(frozen=True, slots=True)
class ArchiveScan:
    records: tuple[ArchiveRecord, ...]
    issues: tuple[ArchiveIssue, ...]

    def by_event_id(self) -> dict[str, ArchiveRecord]:
        return {record.event_id: record for record in self.records if record.event_id}


def escape_field(value: str) -> str:
    """Escape a value so one record always occupies one physical line."""
    output: list[str] = []
    for character in value:
        code = ord(character)
        if character == "\\":
            output.append("\\\\")
        elif character == "\t":
            output.append("\\t")
        elif character == "\n":
            output.append("\\n")
        elif character == "\r":
            output.append("\\r")
        elif code < 32 or code == 127:
            output.append(f"\\x{code:02x}")
        else:
            output.append(character)
    return "".join(output)


def unescape_field(value: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character != "\\":
            output.append(character)
            index += 1
            continue
        if index + 1 >= len(value):
            raise ValueError("field ends with an incomplete escape")
        marker = value[index + 1]
        if marker == "\\":
            output.append("\\")
            index += 2
        elif marker == "t":
            output.append("\t")
            index += 2
        elif marker == "n":
            output.append("\n")
            index += 2
        elif marker == "r":
            output.append("\r")
            index += 2
        elif marker == "x" and index + 3 < len(value):
            raw = value[index + 2 : index + 4]
            try:
                output.append(chr(int(raw, 16)))
            except ValueError as error:
                raise ValueError(f"invalid hex escape: {raw}") from error
            index += 4
        else:
            raise ValueError(f"unsupported escape: \\{marker}")
    return "".join(output)


def encode_record(record: ArchiveRecord) -> str:
    fields = (
        ARCHIVE_MAGIC,
        str(ARCHIVE_VERSION),
        record.recorded_at.isoformat(),
        record.kind,
        record.event_id,
        record.correlation_id,
        record.actor,
        record.payload,
        "",  # Reserved for a backwards-compatible future field.
    )
    return "\t".join(escape_field(value) for value in fields) + "\n"


def decode_record(line: str) -> ArchiveRecord:
    if line.endswith("\n"):
        line = line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    fields = line.split("\t")
    if len(fields) != ARCHIVE_FIELDS:
        raise ValueError(f"expected {ARCHIVE_FIELDS} fields, found {len(fields)}")
    values = [unescape_field(value) for value in fields]
    if values[0] != ARCHIVE_MAGIC:
        raise ValueError("archive magic is invalid")
    if values[1] != str(ARCHIVE_VERSION):
        raise ValueError(f"unsupported archive version: {values[1]}")
    return ArchiveRecord(
        recorded_at=datetime.fromisoformat(values[2]),
        kind=values[3],
        event_id=values[4],
        correlation_id=values[5],
        actor=values[6],
        payload=values[7],
    )


class TextEventArchive:
    """Append records immediately and retain all rotated segments."""

    def __init__(self, directory: Path, *, rotation_bytes: int = 10_000_000) -> None:
        if rotation_bytes < 256:
            raise ValueError("rotation_bytes must be at least 256")
        self.directory = directory
        self.rotation_bytes = rotation_bytes
        self.active_path = directory / "events.log"
        self.directory.mkdir(parents=True, exist_ok=True)
        scan = self.scan()
        self.startup_issues = scan.issues
        self._event_ids = set(scan.by_event_id())

    def append(self, record: ArchiveRecord) -> bool:
        """Append and flush one record; duplicate non-empty event IDs are idempotent."""
        if record.event_id and record.event_id in self._event_ids:
            return False
        encoded = encode_record(record).encode("utf-8")
        if self._should_rotate(len(encoded)):
            self._rotate()
        with self.active_path.open("ab") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if record.event_id:
            self._event_ids.add(record.event_id)
        return True

    def scan(self) -> ArchiveScan:
        records: list[ArchiveRecord] = []
        issues: list[ArchiveIssue] = []
        for path in self.segment_paths():
            raw_lines = path.read_bytes().splitlines(keepends=True)
            for line_number, raw_line in enumerate(raw_lines, start=1):
                if not raw_line.endswith((b"\n", b"\r\n")):
                    issues.append(ArchiveIssue(path, line_number, "truncated final record"))
                    continue
                try:
                    line = raw_line.decode("utf-8")
                    records.append(decode_record(line))
                except (UnicodeDecodeError, ValueError, ArchivePrivacyError) as error:
                    issues.append(ArchiveIssue(path, line_number, str(error)))
        return ArchiveScan(tuple(records), tuple(issues))

    def iter_records(self) -> Iterable[ArchiveRecord]:
        return iter(self.scan().records)

    def segment_paths(self) -> tuple[Path, ...]:
        rotated = sorted(self.directory.glob("events.[0-9][0-9][0-9][0-9][0-9][0-9].log"))
        return tuple(rotated + ([self.active_path] if self.active_path.exists() else []))

    def _should_rotate(self, incoming_bytes: int) -> bool:
        return (
            self.active_path.exists()
            and self.active_path.stat().st_size > 0
            and self.active_path.stat().st_size + incoming_bytes > self.rotation_bytes
        )

    def _rotate(self) -> None:
        sequence = 1
        while (self.directory / f"events.{sequence:06d}.log").exists():
            sequence += 1
        os.replace(self.active_path, self.directory / f"events.{sequence:06d}.log")


def _reject_sensitive(value: str) -> None:
    if "\x00" in value:
        raise ArchivePrivacyError("NUL is not permitted in archive fields")
    if any(pattern.search(value) for pattern in SENSITIVE_PATTERNS):
        raise ArchivePrivacyError("secret-shaped content cannot be archived")


def redact_sensitive(value: str) -> str:
    """Redact secret-shaped substrings without reading any real credential."""
    redacted = value
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted.replace("\x00", "�")
