from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from jimbo_full_bot.live_state import FixedLiveStateProvider, SNAPSHOT_COMMAND


class FixedLiveStateTests(unittest.TestCase):
    def test_fixed_query_parses_snapshot(self) -> None:
        mock_transport = MagicMock()
        mock_transport.command.return_value = (
            "JIMBO_FULL_STATE|players=Alice,Bob|research=rocket-silo|progress=0.125|tick=216000|surfaces=aquilo,nauvis"
        )
        state = FixedLiveStateProvider(transport=mock_transport).collect()
        mock_transport.command.assert_called_once_with(SNAPSHOT_COMMAND)
        self.assertEqual(state.players, ("Alice", "Bob"))
        self.assertEqual(state.answer("research"), "Current research: rocket-silo (12.5%).")
        self.assertEqual(state.answer("game_time"), "The save has run for about 1h 0m of game time.")
        self.assertEqual(state.answer("surfaces"), "Available surfaces: aquilo, nauvis.")

    def test_selected_tools_share_one_fixed_snapshot_with_provenance(self) -> None:
        mock_transport = MagicMock()
        mock_transport.command.return_value = (
            "JIMBO_FULL_STATE|players=Alice|research=none|progress=0.000|tick=3600|surfaces=nauvis"
        )
        provider = FixedLiveStateProvider(transport=mock_transport)
        results = provider.execute(("get_connected_players", "get_game_time"))
        self.assertEqual(mock_transport.command.call_count, 1)
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
