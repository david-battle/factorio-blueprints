"""Offline acceptance tests for Full Bot Step 2 flat-file storage."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from jimbo_full_bot.archive import (
    ArchivePrivacyError,
    ArchiveRecord,
    TextEventArchive,
    decode_record,
    encode_record,
    escape_field,
    unescape_field,
)
from jimbo_full_bot.state import FlatTextStateStore, STATE_NAMES, StateError


BASE_TIME = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def record(index: int, *, payload: str | None = None) -> ArchiveRecord:
    return ArchiveRecord(
        kind="public_chat",
        recorded_at=BASE_TIME + timedelta(seconds=index),
        event_id=f"event-{index}",
        correlation_id=f"request-{index}",
        actor="player",
        payload=payload if payload is not None else f"message {index}",
    )


class ArchiveFormatTests(unittest.TestCase):
    def test_escape_round_trip_keeps_one_physical_line(self) -> None:
        value = "tab\tnewline\nreturn\rslash\\control\x01 Flürki"
        encoded = escape_field(value)

        self.assertNotIn("\t", encoded)
        self.assertNotIn("\n", encoded)
        self.assertNotIn("\r", encoded)
        self.assertEqual(unescape_field(encoded), value)

    def test_record_round_trip_preserves_all_fields(self) -> None:
        original = record(1, payload="hello\nsecond line\tand tab\\")
        encoded = encode_record(original)

        self.assertEqual(encoded.count("\n"), 1)
        self.assertEqual(decode_record(encoded), original)

    def test_invalid_or_incomplete_escapes_are_rejected(self) -> None:
        for value in ("ends\\", "bad\\q", "bad\\xzz"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                unescape_field(value)

    def test_secret_shaped_content_is_rejected_before_serialization(self) -> None:
        secrets = (
            "GROQ_API_KEY=actual-secret",
            "Authorization: Bearer actual-secret",
            "rcon_password=actual-secret",
            "system_prompt=internal-policy-text",
        )
        for secret in secrets:
            with self.subTest(secret=secret), self.assertRaises(ArchivePrivacyError):
                record(1, payload=secret)


class TextEventArchiveTests(unittest.TestCase):
    def test_append_is_immediately_visible_and_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            archive = TextEventArchive(path)

            self.assertTrue(archive.append(record(1)))
            self.assertIn("message 1", (path / "events.log").read_text("utf-8"))

            reopened = TextEventArchive(path)
            self.assertEqual(tuple(reopened.iter_records()), (record(1),))

    def test_duplicate_event_id_is_idempotent_across_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            archive = TextEventArchive(path)
            self.assertTrue(archive.append(record(1)))
            self.assertFalse(archive.append(record(1, payload="different")))

            reopened = TextEventArchive(path)
            self.assertFalse(reopened.append(record(1)))
            self.assertEqual(len(tuple(reopened.iter_records())), 1)

    def test_rotation_retains_and_iterates_all_segments_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = TextEventArchive(Path(directory), rotation_bytes=256)
            expected = tuple(record(index, payload="x" * 120) for index in range(4))
            for item in expected:
                archive.append(item)

            self.assertGreater(len(archive.segment_paths()), 1)
            self.assertEqual(tuple(archive.iter_records()), expected)

    def test_truncated_tail_is_reported_without_losing_prior_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            archive = TextEventArchive(path)
            archive.append(record(1))
            with (path / "events.log").open("ab") as stream:
                stream.write(b"JIMBO_EVENT\t1\tincomplete")

            scan = TextEventArchive(path).scan()

            self.assertEqual(scan.records, (record(1),))
            self.assertEqual(len(scan.issues), 1)
            self.assertIn("truncated final record", scan.issues[0].reason)

    def test_malformed_complete_line_is_reported_and_later_records_survive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            active = path / "events.log"
            active.write_bytes(
                encode_record(record(1)).encode("utf-8")
                + b"not-an-archive-record\n"
                + encode_record(record(2)).encode("utf-8")
            )

            scan = TextEventArchive(path).scan()

            self.assertEqual(scan.records, (record(1), record(2)))
            self.assertEqual(len(scan.issues), 1)

    def test_in_memory_event_index_rebuilds_from_text_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = TextEventArchive(Path(directory))
            archive.append(record(1))
            archive.append(record(2))

            rebuilt = archive.scan().by_event_id()

            self.assertEqual(set(rebuilt), {"event-1", "event-2"})
            self.assertEqual(rebuilt["event-2"].payload, "message 2")

    def test_complete_request_lifecycle_reconstructs_from_archive_alone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            archive = TextEventArchive(path)
            lifecycle = (
                ArchiveRecord("public_chat", BASE_TIME, "Jimbo who is online?", "event-1", "request-1", "Alice"),
                ArchiveRecord("routing", BASE_TIME, "route=direct_live_query", "", "request-1", "Alice"),
                ArchiveRecord("tool", BASE_TIME, "status=complete; players=Alice,Bob", "", "request-1", ""),
                ArchiveRecord("model", BASE_TIME, "raw=Alice and Bob are online.", "", "request-1", ""),
                ArchiveRecord("render", BASE_TIME, "Jimbo to Alice: Alice and Bob are online.", "", "request-1", "Alice"),
                ArchiveRecord("delivery", BASE_TIME, "status=complete", "", "request-1", "Alice"),
            )
            for item in lifecycle:
                archive.append(item)

            reconstructed = tuple(TextEventArchive(path).iter_records())

            self.assertEqual(reconstructed, lifecycle)
            self.assertEqual(
                [item.kind for item in reconstructed],
                ["public_chat", "routing", "tool", "model", "render", "delivery"],
            )
            self.assertTrue(all(item.correlation_id == "request-1" for item in reconstructed))


class FlatTextStateStoreTests(unittest.TestCase):
    def test_every_declared_state_file_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = FlatTextStateStore(Path(directory))
            for name in STATE_NAMES:
                values = {"schema": "example", "value": "line one\nline two\tFlürki"}
                store.replace(name, values)
                self.assertEqual(store.load(name), values)

    def test_state_file_is_human_readable_versioned_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            store = FlatTextStateStore(path)
            store.replace("cursor", {"byte_offset": "123", "source": "server-log"})

            contents = (path / "cursor.state").read_text("utf-8")

            self.assertTrue(contents.startswith("JIMBO_STATE\t1\tcursor\n"))
            self.assertIn("byte_offset\t123\n", contents)
            self.assertNotIn("{", contents)

    def test_interrupted_replace_preserves_previous_complete_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = FlatTextStateStore(Path(directory))
            store.replace("cursor", {"byte_offset": "10"})

            with patch("jimbo_full_bot.state.os.replace", side_effect=OSError("stop")):
                with self.assertRaises(OSError):
                    store.replace("cursor", {"byte_offset": "20"})

            self.assertEqual(store.load("cursor"), {"byte_offset": "10"})
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_legacy_key_value_fixture_migrates_with_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            legacy = path / "cursor.state"
            legacy.write_text("byte_offset=42\nsource=old-log\n", encoding="utf-8")
            store = FlatTextStateStore(path)

            values = store.load("cursor")

            self.assertEqual(values, {"byte_offset": "42", "source": "old-log"})
            self.assertTrue((path / "cursor.state.v0.bak").exists())
            self.assertTrue(legacy.read_text("utf-8").startswith("JIMBO_STATE\t1\tcursor"))

    def test_integrity_check_reports_bad_file_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "preferences.state").write_text("broken\n", encoding="utf-8")
            store = FlatTextStateStore(path)

            issues = store.integrity_check()

            self.assertEqual(len(issues), 1)
            self.assertIn("preferences", issues[0])

    def test_unknown_file_and_invalid_key_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = FlatTextStateStore(Path(directory))
            with self.assertRaisesRegex(StateError, "unknown state file"):
                store.replace("anything", {})
            with self.assertRaisesRegex(StateError, "invalid state key"):
                store.replace("cursor", {"bad key": "value"})


if __name__ == "__main__":
    unittest.main()
