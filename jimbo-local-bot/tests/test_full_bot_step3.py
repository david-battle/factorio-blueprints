"""Offline first-pass tests for Full Bot Step 3 ingestion."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC
from pathlib import Path
from unittest.mock import patch

from jimbo_full_bot.archive import ArchiveRecord, TextEventArchive
from jimbo_full_bot.contracts import EventKind
from jimbo_full_bot.ingestion import (
    DurableLogReader,
    FactorioEventNormalizer,
    LogIngestionService,
    SourceLine,
    event_from_archive_record,
    event_identity,
    event_to_archive_record,
)
from jimbo_full_bot.state import FlatTextStateStore


CHAT = "2026-07-21 10:00:00 [CHAT] Alice: Jimbo hello"
JOIN = "2026-07-21 10:00:01 [JOIN] Bob joined the game"
LEAVE = "2026-07-21 10:00:02 [LEAVE] Bob left the game"


def make_stack(root: Path, *, start_at_end: bool = False) -> tuple[
    Path, FlatTextStateStore, TextEventArchive, DurableLogReader, LogIngestionService
]:
    log = root / "server-console.log"
    if not log.exists():
        log.write_bytes(b"")
    state = FlatTextStateStore(root / "state")
    archive = TextEventArchive(root / "archive")
    reader = DurableLogReader(log, state, start_at_end=start_at_end)
    service = LogIngestionService(reader, archive, FactorioEventNormalizer(source_timezone=UTC))
    return log, state, archive, reader, service


class EventNormalizerTests(unittest.TestCase):
    def source_line(self, text: str) -> SourceLine:
        raw = (text + "\n").encode("utf-8")
        return SourceLine("source-1", 10, 10 + len(raw), raw, text)

    def test_normalizes_chat_join_and_leave(self) -> None:
        normalizer = FactorioEventNormalizer(source_timezone=UTC)

        chat = normalizer.normalize(self.source_line(CHAT))
        join = normalizer.normalize(self.source_line(JOIN))
        leave = normalizer.normalize(self.source_line(LEAVE))

        assert chat is not None and join is not None and leave is not None
        self.assertEqual(chat.kind, EventKind.PUBLIC_CHAT)
        self.assertEqual(chat.actor, "Alice")
        self.assertEqual(chat.message, "Jimbo hello")
        self.assertEqual(join.kind, EventKind.PLAYER_JOIN)
        self.assertEqual(join.actor, "Bob")
        self.assertEqual(leave.kind, EventKind.PLAYER_LEAVE)
        self.assertEqual(leave.occurred_at.tzinfo, UTC)

    def test_unsupported_and_empty_player_records_are_not_events(self) -> None:
        normalizer = FactorioEventNormalizer(source_timezone=UTC)

        self.assertIsNone(normalizer.normalize(self.source_line("diagnostic text")))
        self.assertIsNone(
            normalizer.normalize(
                self.source_line("2026-07-21 10:00:00 [CHAT]  : hello")
            )
        )

    def test_event_id_is_deterministic_and_source_position_specific(self) -> None:
        line = self.source_line(CHAT)
        same = self.source_line(CHAT)
        moved = SourceLine(
            line.source_instance,
            11,
            line.byte_end + 1,
            line.raw_bytes,
            line.text,
        )

        self.assertEqual(event_identity(line), event_identity(same))
        self.assertNotEqual(event_identity(line), event_identity(moved))

    def test_normalized_event_round_trips_through_text_archive_record(self) -> None:
        event = FactorioEventNormalizer(source_timezone=UTC).normalize(
            self.source_line(CHAT)
        )
        assert event is not None

        rebuilt = event_from_archive_record(event_to_archive_record(event))

        self.assertEqual(rebuilt, event)


class DurableIngestionTests(unittest.TestCase):
    def test_first_start_at_end_ignores_history_but_reads_new_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "server-console.log"
            log.write_text(CHAT + "\n", encoding="utf-8")
            _, _, _, reader, service = make_stack(root, start_at_end=True)

            self.assertEqual(reader.transition, "started_at_end")
            self.assertEqual(service.ingest_available().events, ())
            with log.open("a", encoding="utf-8") as stream:
                stream.write(JOIN + "\n")

            batch = service.ingest_available()
            self.assertEqual([event.kind for event in batch.events], [EventKind.PLAYER_JOIN])

    def test_partial_line_is_not_archived_or_committed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log, state, archive, _, service = make_stack(root)
            log.write_bytes(CHAT.encode("utf-8"))

            self.assertEqual(service.ingest_available().events, ())
            self.assertEqual(tuple(archive.iter_records()), ())
            self.assertEqual(state.load("cursor")["byte_offset"], "0")

            with log.open("ab") as stream:
                stream.write(b"\n")
            self.assertEqual(len(service.ingest_available().events), 1)

    def test_records_written_while_stopped_are_ingested_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log, state, archive, _, service = make_stack(root)
            log.write_text(CHAT + "\n", encoding="utf-8")
            self.assertEqual(len(service.ingest_available().events), 1)

            with log.open("a", encoding="utf-8") as stream:
                stream.write(JOIN + "\n" + LEAVE + "\n")
            restarted_reader = DurableLogReader(log, state)
            restarted = LogIngestionService(
                restarted_reader,
                archive,
                FactorioEventNormalizer(source_timezone=UTC),
            )

            batch = restarted.ingest_available()

            self.assertEqual(restarted_reader.transition, "resumed")
            self.assertEqual(
                [event.kind for event in batch.events],
                [EventKind.PLAYER_JOIN, EventKind.PLAYER_LEAVE],
            )
            self.assertEqual(len(tuple(archive.iter_records())), 3)

    def test_archive_happens_before_cursor_commit_and_retry_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log, state, archive, _, service = make_stack(root)
            log.write_text(CHAT + "\n", encoding="utf-8")

            with patch.object(archive, "append", side_effect=OSError("archive unavailable")):
                with self.assertRaises(OSError):
                    service.ingest_available()
            self.assertEqual(state.load("cursor")["byte_offset"], "0")

            self.assertEqual(len(service.ingest_available().events), 1)
            self.assertEqual(len(tuple(archive.iter_records())), 1)

            # Simulate a crash after archive append but before cursor commit.
            state.replace(
                "cursor",
                {
                    "source_instance": service.reader.source_instance,
                    "log_path": str(log.resolve()),
                    "byte_offset": "0",
                    "checkpoint_hex": "",
                    "last_event_id": "",
                },
            )
            replay_reader = DurableLogReader(log, state)
            replay = LogIngestionService(
                replay_reader, archive, FactorioEventNormalizer(source_timezone=UTC)
            )
            self.assertEqual(len(replay.ingest_available().events), 1)
            self.assertEqual(len(tuple(archive.iter_records())), 1)

    def test_truncation_and_replacement_restart_from_new_file_beginning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log, state, archive, reader, service = make_stack(root)
            log.write_text(CHAT + "\n", encoding="utf-8")
            service.ingest_available()

            log.write_text(JOIN + "\n", encoding="utf-8")
            truncated = service.ingest_available()
            self.assertEqual(reader.transition, "truncated")
            self.assertEqual(truncated.events[0].kind, EventKind.PLAYER_JOIN)

            previous = root / "server-console.previous.log"
            log.replace(previous)
            log.write_text(LEAVE + "\n", encoding="utf-8")
            replaced = service.ingest_available()
            self.assertEqual(reader.transition, "rotated")
            self.assertEqual(replaced.events[0].kind, EventKind.PLAYER_LEAVE)
            self.assertEqual(len(tuple(archive.iter_records())), 3)

    def test_malformed_lines_become_bounded_diagnostics_and_advance_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log, state, archive, _, service = make_stack(root)
            log.write_text("not a supported record " + "x" * 800 + "\n", encoding="utf-8")

            batch = service.ingest_available()
            records = tuple(archive.iter_records())

            self.assertEqual(batch.events, ())
            self.assertEqual(batch.diagnostics, 1)
            self.assertEqual(records[0].kind, "diagnostic")
            self.assertLessEqual(len(records[0].payload), 525)
            self.assertGreater(int(state.load("cursor")["byte_offset"]), 0)

    def test_secret_shaped_chat_is_redacted_in_archive_without_blocking_ingestion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log, _, archive, _, service = make_stack(root)
            log.write_text(
                "2026-07-21 10:00:00 [CHAT] Alice: GROQ_API_KEY=do-not-store\n",
                encoding="utf-8",
            )

            batch = service.ingest_available()
            archived = tuple(archive.iter_records())[0]

            self.assertEqual(len(batch.events), 1)
            self.assertNotIn("do-not-store", archived.payload)
            self.assertIn("REDACTED", archived.payload)


if __name__ == "__main__":
    unittest.main()
