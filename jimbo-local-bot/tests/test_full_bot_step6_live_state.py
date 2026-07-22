from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from jimbo_full_bot.live_state import FixedLiveStateProvider, SNAPSHOT_COMMAND


class FixedLiveStateTests(unittest.TestCase):
    @patch("jimbo_full_bot.live_state.subprocess.run")
    def test_fixed_query_parses_snapshot_and_restores_command(self, run: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / "command.txt"
            command.write_text("/players\n", encoding="utf-8")
            original = command.read_bytes()
            def result(*_args, **_kwargs):
                self.assertEqual(command.read_text(encoding="utf-8").strip(), SNAPSHOT_COMMAND)
                return CompletedProcess([], 0,
                    "JIMBO_FULL_STATE|players=Alice,Bob|research=rocket-silo|progress=0.125|tick=216000|surfaces=aquilo,nauvis", "")
            run.side_effect = result
            state = FixedLiveStateProvider(
                wrapper_path=Path("wrapper.ps1"), command_path=command, timeout_seconds=5
            ).collect()
            self.assertEqual(state.players, ("Alice", "Bob"))
            self.assertEqual(state.answer("research"), "Current research: rocket-silo (12.5%).")
            self.assertEqual(state.answer("game_time"), "The save has run for about 1h 0m of game time.")
            self.assertEqual(state.answer("surfaces"), "Available surfaces: aquilo, nauvis.")
            self.assertEqual(command.read_bytes(), original)

    @patch("jimbo_full_bot.live_state.subprocess.run")
    def test_selected_tools_share_one_fixed_snapshot_with_provenance(self, run: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / "command.txt"
            command.write_text("/players\n", encoding="utf-8")
            run.return_value = CompletedProcess([], 0,
                "JIMBO_FULL_STATE|players=Alice|research=none|progress=0.000|tick=3600|surfaces=nauvis", "")
            provider = FixedLiveStateProvider(
                wrapper_path=Path("wrapper.ps1"), command_path=command, timeout_seconds=5
            )
            results = provider.execute(("get_connected_players", "get_game_time"))
            self.assertEqual(run.call_count, 1)
            self.assertEqual(results[0].values["operation"], "get_connected_players")
            self.assertEqual(results[1].values["operation"], "get_game_time")
            self.assertEqual(results[0].provenance.collected_at,
                             results[1].provenance.collected_at)
            self.assertTrue(results[0].provenance.complete)

    def test_direct_answers_are_bounded_and_transparent(self) -> None:
        from jimbo_full_bot.live_state import LiveServerState
        state = LiveServerState((), None, 0.0, 0, ())
        self.assertEqual(state.answer("players"), "Online players: none.")
        self.assertEqual(state.answer("research"), "No research is currently active.")


if __name__ == "__main__":
    unittest.main()
