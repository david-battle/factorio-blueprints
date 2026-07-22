"""Quota-free tests for the minimal Step 10 free-form RCON bridge."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from jimbo_full_bot.contracts import ResultStatus
from jimbo_full_bot.freeform_rcon import FreeformRconError, FreeformRconProvider


class FreeformRconProviderTests(unittest.TestCase):
    def provider(self) -> FreeformRconProvider:
        return FreeformRconProvider(transport=MagicMock())

    def test_executes_model_command_and_captures_output(self) -> None:
        mock_transport = MagicMock()
        mock_transport.command.return_value = '{"count":7}\n'
        result = FreeformRconProvider(transport=mock_transport).execute(
            "/silent-command rcon.print(helpers.table_to_json({count=7}))"
        )
        mock_transport.command.assert_called_once()
        sent_command = mock_transport.command.call_args[0][0]
        self.assertIn("/silent-command rcon.print(helpers.table_to_json({count=7}))", sent_command)
        self.assertEqual(result.status, ResultStatus.COMPLETE)
        self.assertIn('"count":7', result.values["output"])

    def test_failure_raises_freeform_rcon_error(self) -> None:
        mock_transport = MagicMock()
        mock_transport.command.side_effect = Exception("connection refused")
        with self.assertRaises(FreeformRconError):
            FreeformRconProvider(transport=mock_transport).execute(
                "/silent-command rcon.print(1)"
            )


if __name__ == "__main__":
    unittest.main()
