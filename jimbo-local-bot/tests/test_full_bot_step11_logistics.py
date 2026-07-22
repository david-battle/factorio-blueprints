"""Quota-free tests for the bounded logistics/storage adapter."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from jimbo_full_bot.contracts import ResultStatus
from jimbo_full_bot.investigation import InvestigationPlanError, validate_steps
from jimbo_full_bot.logistics_state import LogisticsInvestigationProvider, LOGISTICS_MARKER


SNAPSHOT = {
    "networks": [{
        "id": 2, "name": "Nauvis Main", "surface": "nauvis",
        "position": {"x": 88, "y": 129},
        "available_logistic_robots": 573, "total_logistic_robots": 722,
        "available_construction_robots": 0, "total_construction_robots": 670,
        "roboports": 99, "providers": 168, "requesters": 15, "storages": 67,
        "contents": [
            {"name": "steel-plate", "quality": "normal", "count": 100},
            {"name": "repair-pack", "quality": "normal", "count": 436},
        ],
    }],
    "containers": [{
        "unit_number": 44, "prototype": "requester-chest", "surface": "nauvis",
        "position": {"x": 90, "y": 130}, "network_id": 2,
        "inventory": [{"name": "steel-plate", "quality": "normal", "count": 5}],
        "requests": [{"name": "steel-plate", "quality": "normal", "min": 100}],
    }],
    "warnings": [],
}


class LogisticsValidationTests(unittest.TestCase):
    def test_accepts_registered_operations_and_rejects_fuzzy_or_extra_arguments(self) -> None:
        steps = validate_steps([
            {"op": "list_networks", "domain": "logistics", "surface": "nauvis"},
            {"op": "inspect_contents", "domain": "logistics", "network": 2, "item": "steel-plate"},
            {"op": "inspect_containers", "domain": "logistics", "network": "Nauvis Main", "prototype": "requester-chest"},
            {"op": "count_items", "domain": "logistics", "surface": "nauvis", "item": "steel-plate", "member": "providers"},
        ])
        self.assertEqual(len(steps), 4)
        with self.assertRaises(InvestigationPlanError):
            validate_steps([{"op": "inspect_contents", "domain": "logistics", "near": "main base"}])


class LogisticsProviderTests(unittest.TestCase):
    @patch("jimbo_full_bot.logistics_state.subprocess.run")
    def test_one_fixed_snapshot_supports_networks_contents_and_containers(self, run: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / "command.txt"
            command.write_text("/players\n", encoding="utf-8")
            original = command.read_bytes()
            run.return_value = CompletedProcess([], 0, LOGISTICS_MARKER + json.dumps(SNAPSHOT), "")
            results = LogisticsInvestigationProvider(
                wrapper_path=Path("wrapper.ps1"), command_path=command, timeout_seconds=5,
            ).execute((
                {"op": "list_networks", "domain": "logistics", "select": ["id", "name", "available_construction_robots"]},
                {"op": "inspect_contents", "domain": "logistics", "network": 2, "item": "steel-plate"},
                {"op": "inspect_containers", "domain": "logistics", "network": 2, "prototype": "requester-chest"},
            ))
            self.assertEqual(run.call_count, 3)
            self.assertEqual(command.read_bytes(), original)
            self.assertEqual(results[0].values["results"][0]["available_construction_robots"], 0)
            self.assertEqual(results[1].values["results"][0]["items"][0]["count"], 100)
            self.assertEqual(results[2].values["results"][0]["requests"][0]["min"], 100)
            self.assertTrue(all(result.provenance is not None for result in results))

    @patch("jimbo_full_bot.logistics_state.subprocess.run")
    def test_exact_network_miss_returns_candidates(self, run: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / "command.txt"
            command.write_text("/players\n", encoding="utf-8")
            run.return_value = CompletedProcess([], 0, LOGISTICS_MARKER + json.dumps(SNAPSHOT), "")
            result = LogisticsInvestigationProvider(
                wrapper_path=Path("wrapper.ps1"), command_path=command, timeout_seconds=5,
            ).execute(({"op": "inspect_contents", "domain": "logistics", "network": "main"},))[0]
            self.assertEqual(result.status, ResultStatus.UNKNOWN)
            self.assertEqual(result.values["candidates"][0]["id"], 2)

    @patch("jimbo_full_bot.logistics_state.subprocess.run")
    def test_direct_item_count_avoids_inventory_row_dump(self, run: object) -> None:
        counted = {"networks": [{"id": 2, "name": "Nauvis Main", "surface": "nauvis", "count": 17}],
                   "containers": [], "warnings": []}
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / "command.txt"
            command.write_text("/players\n", encoding="utf-8")
            run.return_value = CompletedProcess([], 0, LOGISTICS_MARKER + json.dumps(counted), "")
            result = LogisticsInvestigationProvider(
                wrapper_path=Path("wrapper.ps1"), command_path=command, timeout_seconds=5,
            ).execute(({"op": "count_items", "domain": "logistics", "network": 2,
                        "item": "steel-plate", "member": "providers"},))[0]
            self.assertEqual(result.values["results"][0]["count"], 17)
            self.assertEqual(result.values["results"][0]["member"], "providers")
            self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
