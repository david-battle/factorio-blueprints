"""Quota-free tests for the minimal Step 10 free-form RCON bridge."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jimbo_full_bot.contracts import ResultStatus
from jimbo_full_bot.freeform_rcon import FreeformRconError, FreeformRconProvider


class FreeformRconProviderTests(unittest.TestCase):
    def provider(self, root: Path) -> FreeformRconProvider:
        return FreeformRconProvider(
            wrapper_path=root / "wrapper.ps1",
            command_path=root / "command.txt",
            timeout_seconds=3,
        )

    @patch("jimbo_full_bot.freeform_rcon.subprocess.run")
    def test_executes_model_command_captures_output_and_restores_file(self, run) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            command_path = root / "command.txt"
            command_path.write_text("/players\n", encoding="utf-8")
            observed = []

            def complete(*args, **kwargs):
                observed.append(command_path.read_text(encoding="utf-8"))
                return subprocess.CompletedProcess(args[0], 0, "{\"count\":7}\n", "")

            run.side_effect = complete
            result = self.provider(root).execute(
                "/silent-command rcon.print(helpers.table_to_json({count=7}))"
            )
            self.assertEqual(observed, [
                "/silent-command rcon.print(helpers.table_to_json({count=7}))\n"
            ])
            self.assertEqual(command_path.read_text(encoding="utf-8"), "/players\n")
            self.assertEqual(result.status, ResultStatus.COMPLETE)
            self.assertIn('"count":7', result.values["output"])

    @patch("jimbo_full_bot.freeform_rcon.subprocess.run")
    def test_failure_still_restores_command_file(self, run) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            command_path = root / "command.txt"
            command_path.write_text("/players\n", encoding="utf-8")
            run.return_value = subprocess.CompletedProcess([], 1, "", "bad command")
            with self.assertRaises(FreeformRconError):
                self.provider(root).execute("/silent-command rcon.print(1)")
            self.assertEqual(command_path.read_text(encoding="utf-8"), "/players\n")


if __name__ == "__main__":
    unittest.main()
