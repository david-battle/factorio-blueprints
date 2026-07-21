"""Minimal durable Factorio log ingestion for Full Bot Step 3."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from .archive import ArchiveRecord, TextEventArchive, redact_sensitive
from .contracts import EventKind, NormalizedEvent
from .state import FlatTextStateStore, StateError


TIMESTAMP = r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
CHAT_RE = re.compile(
    rf"^{TIMESTAMP} \[CHAT\] (?P<player>[^:]+): (?P<message>.*)$"
)
JOIN_RE = re.compile(
    rf"^{TIMESTAMP} \[JOIN\] (?P<player>.+?) joined(?: the game)?$"
)
LEAVE_RE = re.compile(
    rf"^{TIMESTAMP} \[LEAVE\] (?P<player>.+?) left(?: the game)?$"
)
DEFAULT_TIMEZONE = datetime.now().astimezone().tzinfo or UTC
CHECKPOINT_BYTES = 128


@dataclass(frozen=True, slots=True)
class SourceLine:
    source_instance: str
    byte_start: int
    byte_end: int
    raw_bytes: bytes
    text: str


@dataclass(frozen=True, slots=True)
class IngestionBatch:
    events: tuple[NormalizedEvent, ...]
    diagnostics: int
    transition: str


class DurableLogReader:
    """Read only complete uncommitted lines from one Factorio log."""

    def __init__(
        self,
        path: Path,
        state: FlatTextStateStore,
        *,
        start_at_end: bool = True,
    ) -> None:
        self.path = path
        self.state = state
        self.start_at_end = start_at_end
        self.transition = "unopened"
        self.source_instance = ""
        self.offset = 0
        self._initialize()

    def read_complete_lines(self) -> tuple[SourceLine, ...]:
        stat = self.path.stat()
        current_identity = source_identity(self.path)
        if current_identity != self.source_instance:
            self.source_instance = current_identity
            self.offset = 0
            self.transition = "rotated"
        elif stat.st_size < self.offset or not self._checkpoint_matches():
            self.offset = 0
            self.transition = "truncated"

        with self.path.open("rb") as stream:
            stream.seek(self.offset)
            data = stream.read()
        if not data:
            return ()
        parts = data.splitlines(keepends=True)
        if parts and not parts[-1].endswith((b"\n", b"\r")):
            parts.pop()
        result: list[SourceLine] = []
        position = self.offset
        for raw in parts:
            end = position + len(raw)
            result.append(
                SourceLine(
                    source_instance=self.source_instance,
                    byte_start=position,
                    byte_end=end,
                    raw_bytes=raw,
                    text=raw.rstrip(b"\r\n").decode("utf-8", errors="replace"),
                )
            )
            position = end
        return tuple(result)

    def commit(self, line: SourceLine, *, last_event_id: str = "") -> None:
        if line.source_instance != self.source_instance:
            raise RuntimeError("cannot commit a line from an obsolete source")
        if line.byte_start != self.offset:
            raise RuntimeError("log lines must be committed in byte order")
        self.offset = line.byte_end
        self.state.replace(
            "cursor",
            {
                "source_instance": self.source_instance,
                "log_path": str(self.path.resolve()),
                "byte_offset": str(self.offset),
                "checkpoint_hex": self._checkpoint_at(self.offset).hex(),
                "last_event_id": last_event_id,
            },
        )

    def _initialize(self) -> None:
        stat = self.path.stat()
        self.source_instance = source_identity(self.path)
        try:
            cursor = self.state.load("cursor")
        except StateError:
            cursor = {}
        if not cursor:
            self.offset = stat.st_size if self.start_at_end else 0
            self.transition = "started_at_end" if self.start_at_end else "started_at_start"
            self._write_initial_cursor()
            return
        try:
            candidate = int(cursor["byte_offset"])
        except (KeyError, ValueError):
            candidate = -1
        if cursor.get("log_path") != str(self.path.resolve()):
            candidate = -1
        if cursor.get("source_instance") != self.source_instance:
            self.offset = 0
            self.transition = "rotated"
        elif not 0 <= candidate <= stat.st_size:
            self.offset = 0
            self.transition = "truncated"
        else:
            self.offset = candidate
            expected = cursor.get("checkpoint_hex", "")
            try:
                checkpoint = bytes.fromhex(expected)
            except ValueError:
                checkpoint = b"invalid"
            if checkpoint != self._checkpoint_at(self.offset):
                self.offset = 0
                self.transition = "truncated"
            else:
                self.transition = "resumed"

    def _write_initial_cursor(self) -> None:
        self.state.replace(
            "cursor",
            {
                "source_instance": self.source_instance,
                "log_path": str(self.path.resolve()),
                "byte_offset": str(self.offset),
                "checkpoint_hex": self._checkpoint_at(self.offset).hex(),
                "last_event_id": "",
            },
        )

    def _checkpoint_matches(self) -> bool:
        try:
            cursor = self.state.load("cursor")
            expected = bytes.fromhex(cursor.get("checkpoint_hex", ""))
        except (StateError, ValueError):
            return False
        return expected == self._checkpoint_at(self.offset)

    def _checkpoint_at(self, offset: int) -> bytes:
        start = max(0, offset - CHECKPOINT_BYTES)
        with self.path.open("rb") as stream:
            stream.seek(start)
            return stream.read(offset - start)


class FactorioEventNormalizer:
    def __init__(self, *, source_timezone: tzinfo = DEFAULT_TIMEZONE) -> None:
        self.source_timezone = source_timezone

    def normalize(self, line: SourceLine) -> NormalizedEvent | None:
        match: re.Match[str] | None
        kind: EventKind
        message: str | None = None
        if (match := CHAT_RE.fullmatch(line.text)) is not None:
            kind = EventKind.PUBLIC_CHAT
            message = match.group("message")
        elif (match := JOIN_RE.fullmatch(line.text)) is not None:
            kind = EventKind.PLAYER_JOIN
        elif (match := LEAVE_RE.fullmatch(line.text)) is not None:
            kind = EventKind.PLAYER_LEAVE
        else:
            return None
        actor = match.group("player").strip()
        if not actor:
            return None
        occurred_at = datetime.strptime(
            match.group("timestamp"), "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=self.source_timezone)
        return NormalizedEvent(
            event_id=event_identity(line),
            kind=kind,
            occurred_at=occurred_at,
            source_instance=line.source_instance,
            byte_start=line.byte_start,
            byte_end=line.byte_end,
            raw_text=line.text,
            actor=actor,
            message=message,
        )


class LogIngestionService:
    """Archive each complete line before committing its source cursor."""

    def __init__(
        self,
        reader: DurableLogReader,
        archive: TextEventArchive,
        normalizer: FactorioEventNormalizer,
    ) -> None:
        self.reader = reader
        self.archive = archive
        self.normalizer = normalizer

    def ingest_available(self) -> IngestionBatch:
        events: list[NormalizedEvent] = []
        diagnostics = 0
        transition = self.reader.transition
        for line in self.reader.read_complete_lines():
            event = self.normalizer.normalize(line)
            if event is None:
                diagnostics += 1
                diagnostic_id = event_identity(line)
                archived = ArchiveRecord(
                    kind="diagnostic",
                    recorded_at=datetime.now(UTC),
                    event_id=diagnostic_id,
                    payload="unsupported_or_malformed=" + redact_sensitive(line.text)[:500],
                )
                self.archive.append(archived)
                self.reader.commit(line, last_event_id=diagnostic_id)
                continue
            self.archive.append(event_to_archive_record(event))
            self.reader.commit(line, last_event_id=event.event_id)
            events.append(event)
        return IngestionBatch(tuple(events), diagnostics, transition)


def event_identity(line: SourceLine) -> str:
    digest = hashlib.sha256()
    digest.update(line.source_instance.encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(line.byte_start).encode("ascii"))
    digest.update(b":")
    digest.update(str(line.byte_end).encode("ascii"))
    digest.update(b"\0")
    digest.update(line.raw_bytes)
    return digest.hexdigest()


def source_identity(path: Path) -> str:
    stat = path.stat()
    inode = stat.st_ino if stat.st_ino else stat.st_ctime_ns
    value = f"{path.resolve()}\0{stat.st_dev}\0{inode}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def event_to_archive_record(event: NormalizedEvent) -> ArchiveRecord:
    payload = urlencode(
        {
            "source": event.source_instance,
            "start": str(event.byte_start),
            "end": str(event.byte_end),
            "occurred": event.occurred_at.isoformat(),
            "raw": redact_sensitive(event.raw_text),
            "message": redact_sensitive(event.message or ""),
        }
    )
    return ArchiveRecord(
        kind=event.kind.value,
        recorded_at=datetime.now(UTC),
        event_id=event.event_id,
        actor=event.actor or "",
        payload=payload,
    )


def event_from_archive_record(record: ArchiveRecord) -> NormalizedEvent:
    if record.kind not in {kind.value for kind in EventKind if kind is not EventKind.DIAGNOSTIC}:
        raise ValueError(f"archive record is not a normalized public event: {record.kind}")
    fields = parse_qs(record.payload, keep_blank_values=True, strict_parsing=True)

    def one(name: str) -> str:
        values = fields.get(name)
        if values is None or len(values) != 1:
            raise ValueError(f"event archive field is missing or repeated: {name}")
        return values[0]

    message = one("message")
    return NormalizedEvent(
        event_id=record.event_id,
        kind=EventKind(record.kind),
        occurred_at=datetime.fromisoformat(one("occurred")),
        source_instance=one("source"),
        byte_start=int(one("start")),
        byte_end=int(one("end")),
        raw_text=one("raw"),
        actor=record.actor or None,
        message=message or None,
    )
