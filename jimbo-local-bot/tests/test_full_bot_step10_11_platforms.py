"""Quota-free tests for the minimal investigation core and platform adapter."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from jimbo_full_bot.contracts import ResultStatus
from jimbo_full_bot.investigation import InvestigationPlanError, validate_steps
from jimbo_full_bot.platform_state import PlatformInvestigationProvider, PLATFORM_MARKER


SNAPSHOT = {
    "platforms": [
        {
            "index": 1, "name": "Science Ship", "surface": "platform-1",
            "state": "waiting_at_station", "paused": True, "speed": 0,
            "weight": 102000, "loc": "nauvis", "has_hub": True,
            "kind": "stopped_at_location", "from": None, "to": None,
            "inventory": [
                {"name": "space-science-pack", "quality": "normal", "count": 10},
                {"name": "iron-plate", "quality": "normal", "count": 80},
            ],
            "requests": [{"name": "solar-panel", "quality": "normal", "min": 20}],
            "schedule": {"current": 1, "records": [{"station": "vulcanus"}]},
        },
        {"index": 3, "name": "Froidulant", "state": "no_schedule",
         "has_hub": False, "inventory": [], "requests": [], "schedule": {}},
    ],
    "warnings": [],
}


class InvestigationValidationTests(unittest.TestCase):
    def test_rejects_unknown_fields_fuzzy_references_and_excessive_steps(self) -> None:
        invalid = (
            [{"op": "list_objects", "domain": "space_platforms", "select": ["secret"]}],
            [{"op": "inspect_inventory", "domain": "space_platforms", "contains": "science"}],
            [{"op": "list_objects", "domain": "space_platforms"}] * 7,
        )
        for steps in invalid:
            with self.subTest(steps=steps), self.assertRaises(InvestigationPlanError):
                validate_steps(steps)


class PlatformProviderTests(unittest.TestCase):
    @patch("jimbo_full_bot.platform_state.subprocess.run")
    def test_one_fixed_snapshot_supports_projection_inventory_requests_and_schedule(
        self, run: object
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / "command.txt"
            command.write_text("/players\n", encoding="utf-8")
            original = command.read_bytes()
            run.return_value = CompletedProcess(
                [], 0, PLATFORM_MARKER + json.dumps(SNAPSHOT, separators=(",", ":")), ""
            )
            provider = PlatformInvestigationProvider(
                wrapper_path=Path("wrapper.ps1"), command_path=command, timeout_seconds=5
            )
            results = provider.execute((
                {"op": "list_objects", "domain": "space_platforms",
                 "select": ["id", "name", "surface", "location", "location_kind"]},
                {"op": "inspect_inventory", "domain": "space_platforms",
                 "platform": 1, "item": "space-science-pack"},
                {"op": "list_requests", "domain": "space_platforms", "platform": 1},
                {"op": "get_schedule", "domain": "space_platforms", "platform": 1},
            ))
            self.assertEqual(run.call_count, 2)
            self.assertEqual(command.read_bytes(), original)
            self.assertEqual(results[0].values["results"][0]["name"], "Science Ship")
            self.assertEqual(results[0].values["results"][0]["location_kind"], "stopped_at_location")
            self.assertEqual(results[1].values["results"][0]["items"][0]["count"], 10)
            self.assertEqual(results[2].values["results"][0]["requests"][0]["name"], "solar-panel")
            self.assertEqual(results[3].values["results"][0]["schedule"]["current"], 1)
            self.assertTrue(all(result.provenance is not None for result in results))

    @patch("jimbo_full_bot.platform_state.subprocess.run")
    def test_exact_reference_miss_returns_candidates_without_fuzzy_choice(self, run: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / "command.txt"
            command.write_text("/players\n", encoding="utf-8")
            run.return_value = CompletedProcess([], 0, PLATFORM_MARKER + json.dumps(SNAPSHOT), "")
            result = PlatformInvestigationProvider(
                wrapper_path=Path("wrapper.ps1"), command_path=command, timeout_seconds=5
            ).execute(({
                "op": "inspect_inventory", "domain": "space_platforms",
                "platform": "science",
            },))[0]
            self.assertEqual(result.status, ResultStatus.UNKNOWN)
            self.assertEqual(len(result.values["candidates"]), 2)


if __name__ == "__main__":
    unittest.main()
