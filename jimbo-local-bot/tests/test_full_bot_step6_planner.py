"""Quota-free tests for the model-directed Step 6 state-needs planner."""

from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime

from jimbo_full_bot.contracts import Provenance, ResultStatus, ToolResult
from jimbo_full_bot.model import GroqModelGateway
from jimbo_full_bot.state_planning import StatePlanError, planning_context, validate_state_plan
from test_full_bot_step7 import FakeResponse, plan


class StatePlanValidationTests(unittest.TestCase):
    def test_accepts_only_allowlisted_unique_names(self) -> None:
        parsed = validate_state_plan(
            '{"subjects":["other"],"tools":["get_connected_players","get_current_research"]}'
        )
        self.assertEqual(parsed.tools, (
            "get_connected_players", "get_current_research"
        ))
        self.assertEqual(validate_state_plan('{"subjects":["other"],"tools":[]}').tools, ())

    def test_accepts_bounded_platform_investigation_steps(self) -> None:
        parsed = validate_state_plan(json.dumps({
            "subjects": ["other"],
            "tools": [],
            "steps": [
                {"op": "list_objects", "domain": "space_platforms",
                 "select": ["id", "name", "surface"]},
                {"op": "inspect_inventory", "domain": "space_platforms",
                 "item": "space-science-pack"},
            ],
        }))
        self.assertEqual(len(parsed.investigation_steps), 2)
        self.assertEqual(parsed.investigation_steps[1]["item"], "space-science-pack")

    def test_accepts_one_freeform_rcon_command(self) -> None:
        command = "/silent-command rcon.print(#game.connected_players)"
        parsed = validate_state_plan(json.dumps({
            "subjects": ["other"], "tools": [], "steps": [], "facts": [],
            "rcon": command,
        }))
        self.assertEqual(parsed.rcon_command, command)

    def test_rejects_malformed_freeform_rcon_commands(self) -> None:
        for command in ("rcon.print(1)", "/silent-command rcon.print(1)\n/players", ""):
            with self.subTest(command=command), self.assertRaises(StatePlanError):
                validate_state_plan(json.dumps({
                    "subjects": ["other"], "tools": [], "rcon": command,
                }))

    def test_accepts_bounded_authoritative_fact_steps(self) -> None:
        parsed = validate_state_plan(json.dumps({
            "subjects": ["jimbo", "named_player"],
            "tools": [],
            "steps": [],
            "facts": [
                {"op": "runtime_identity"},
                {"op": "player_history", "player": "Alice"},
                {"op": "player_permissions", "player": "Bob", "action": "ban"},
            ],
        }))
        self.assertEqual(parsed.fact_steps[1]["player"], "Alice")
        self.assertEqual(parsed.fact_steps[2]["action"], "ban")

    def test_subjects_require_compatible_facts_and_exact_players(self) -> None:
        valid = validate_state_plan(json.dumps({
            "subjects": ["server_owner", "factorio_admins"],
            "tools": [],
            "facts": [
                {"op": "server_identity"},
                {"op": "list_admins", "connected_only": True},
            ],
        }))
        self.assertEqual(valid.subjects, ("server_owner", "factorio_admins"))
        for value in (
            {"subjects": ["server"], "tools": [], "facts": [{"op": "runtime_identity"}]},
            {"subjects": ["server_owner", "factorio_admins"], "tools": [],
             "facts": [{"op": "server_identity"}]},
            {"subjects": ["named_player"], "tools": [],
             "facts": [{"op": "player_permissions", "player": "*", "action": "kick"}]},
            {"subjects": ["jimbo"], "tools": [],
             "facts": [{"op": "player_permissions", "player": "Alice"}]},
        ):
            with self.subTest(value=value), self.assertRaises(StatePlanError):
                validate_state_plan(json.dumps(value))

    def test_normalizes_allowlisted_fact_misplaced_as_investigation_step(self) -> None:
        parsed = validate_state_plan(json.dumps({
            "subjects": ["factorio_admins"],
            "tools": [],
            "steps": [{
                "op": "list_admins", "domain": "factorio_admins",
                "connected_only": True,
            }],
            "facts": [],
        }))
        self.assertEqual(parsed.investigation_steps, ())
        self.assertEqual(parsed.fact_steps, ({
            "op": "list_admins", "connected_only": True,
        },))

    def test_admin_fact_covers_redundant_server_subject(self) -> None:
        parsed = validate_state_plan(json.dumps({
            "subjects": ["server", "factorio_admins"],
            "tools": [],
            "facts": [{"op": "list_admins", "connected_only": True}],
        }))
        self.assertEqual(parsed.subjects, ("factorio_admins",))
        self.assertEqual(parsed.fact_steps[0]["op"], "list_admins")

        inferred = validate_state_plan(json.dumps({
            "subjects": ["server"], "tools": [],
            "facts": [{"op": "list_admins"}],
        }))
        self.assertEqual(inferred.subjects, ("factorio_admins",))

    def test_rejects_incompatible_extra_identity_fact(self) -> None:
        with self.assertRaisesRegex(StatePlanError, "jimbo subject"):
            validate_state_plan(json.dumps({
                "subjects": ["server", "server_owner", "factorio_admins"],
                "tools": [],
                "facts": [
                    {"op": "runtime_identity"}, {"op": "server_identity"},
                    {"op": "list_admins"},
                ],
            }))

    def test_accepts_permission_clarification_without_invented_name(self) -> None:
        parsed = validate_state_plan(json.dumps({
            "subjects": ["named_player"], "tools": [],
            "facts": [{"op": "player_permissions_help"}],
        }))
        self.assertEqual(parsed.fact_steps[0]["op"], "player_permissions_help")

    def test_rejects_extra_fields_arguments_unknown_tools_and_code(self) -> None:
        invalid = (
            '{"tools":[],"reason":"because"}',
            '{"tools":[{"name":"get_game_time","arguments":{}}]}',
            '{"tools":["scan_everything"]}',
            '{"tools":["/silent-command rcon.print(1)"]}',
            '{"tools":["get_game_time","get_game_time"]}',
            '{"tools":[],"steps":[{"op":"delete","domain":"space_platforms"}]}',
            '{"tools":[],"steps":[{"op":"inspect_inventory","domain":"space_platforms","lua":"x"}]}',
            '{"tools":[],"facts":[{"op":"invented"}]}',
            '{"tools":[],"facts":[{"op":"player_history"}]}',
            '{"tools":[],"facts":[{"op":"runtime_identity","player":"Alice"}]}',
            'not json',
        )
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(StatePlanError):
                validate_state_plan(raw)

    def test_planning_context_keeps_history_and_provenance_as_data(self) -> None:
        result = ToolResult(
            ResultStatus.COMPLETE,
            "Online players: Alice.",
            Provenance("fixed_read_only_rcon", datetime(2026, 7, 21, tzinfo=UTC), "server"),
            {"operation": "get_connected_players", "players": ["Alice"]},
        )
        data = json.loads(planning_context(
            "How do you know?", (("Who is online?", "Alice is online."),), (result,)
        ))
        self.assertEqual(data["request"], "How do you know?")
        self.assertEqual(data["recent_exchanges"][0]["player"], "Who is online?")
        self.assertEqual(
            data["most_recent_observations"][0]["provenance"]["source"],
            "fixed_read_only_rcon",
        )


class ModelPlanningTests(unittest.TestCase):
    def test_one_planning_call_describes_freeform_rcon_field(self) -> None:
        captured = []
        def open_request(request, *, timeout):
            captured.append(json.loads(request.data))
            return FakeResponse({"choices": [{"message": {
                "content": '{"subjects":["other"],"tools":["get_available_surfaces"]}'
            }}]})
        gateway = GroqModelGateway(
            api_key="secret", model="test", timeout_seconds=4, opener=open_request
        )
        parsed = gateway.plan_state_needs(
            plan(text="Where can we travel?").plan,
            history=(("What planets exist?", "I need a live observation."),),
        )
        self.assertEqual(parsed.tools, ("get_available_surfaces",))
        self.assertEqual(len(captured), 1)
        messages = captured[0]["messages"]
        self.assertIn("get_connected_players", messages[0]["content"])
        self.assertIn("MUST select runtime_identity", messages[0]["content"])
        self.assertIn("/silent-command", json.dumps(messages))
        self.assertIn("rcon.print", json.dumps(messages))
        self.assertEqual(captured[0]["temperature"], 0.0)

    def test_invalid_first_plan_gets_exactly_one_schema_correction(self) -> None:
        replies = iter((
            {"choices": [{"message": {"content": '{"subjects":["other"],"tools":["invented"]}'}}]},
            {"choices": [{"message": {"content": '{"subjects":["other"],"tools":[],"steps":[]}'}}]},
        ))
        calls = []
        def open_request(request, *, timeout):
            calls.append(json.loads(request.data))
            return FakeResponse(next(replies))
        parsed = GroqModelGateway(
            api_key="secret", model="test", timeout_seconds=4, opener=open_request
        ).plan_state_needs(plan(text="hello").plan)
        self.assertEqual(parsed.tools, ())
        self.assertEqual(len(calls), 2)
        self.assertIn("previous JSON plan was rejected", calls[1]["messages"][-1]["content"])


if __name__ == "__main__":
    unittest.main()
