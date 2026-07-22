"""Offline tests for the intentionally thin Full Bot Step 6 router."""

from __future__ import annotations

import unittest

from jimbo_full_bot.config import FullBotConfig
from jimbo_full_bot.contracts import RouteKind
from jimbo_full_bot.interactions import InvocationDecision
from jimbo_full_bot.routing import MinimalConversationRouter, STATIC_SERVER_CONTEXT


def decision(
    *, actor: str = "Alice", request: str = "hello", accepted: bool = True
) -> InvocationDecision:
    return InvocationDecision(
        event_id="event-1",
        actor=actor,
        accepted=accepted,
        request_text=request if accepted else "",
        reason="accepted" if accepted else "no leading invocation",
    )


class MinimalConversationRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = MinimalConversationRouter(FullBotConfig.offline())

    def test_accepted_invocation_becomes_tool_free_conversation_plan(self) -> None:
        handoff = self.router.route(decision(request="How do I make green circuits?"))

        assert handoff is not None
        self.assertEqual(handoff.plan.route, RouteKind.CONVERSATION)
        self.assertEqual(handoff.plan.request_text, "How do I make green circuits?")
        self.assertEqual(handoff.plan.allowed_tool_families, ())
        self.assertEqual(handoff.plan.correlation_id, "request-event-1")

    def test_rejected_invocation_has_no_handoff(self) -> None:
        self.assertIsNone(self.router.route(decision(accepted=False)))

    def test_only_configured_management_identity_gets_management_flag(self) -> None:
        ordinary = self.router.route(decision(actor="Alice"))
        management = self.router.route(decision(actor="DLBATTLE"))

        assert ordinary is not None and management is not None
        self.assertFalse(ordinary.plan.authority.is_management)
        self.assertTrue(management.plan.authority.is_management)
        self.assertTrue(ordinary.plan.authority.allowed)
        self.assertEqual(ordinary.plan.authority.capability, "conversation")

    def test_static_context_contains_server_blurb_and_no_live_claim(self) -> None:
        handoff = self.router.route(decision())

        assert handoff is not None
        self.assertEqual(handoff.context, STATIC_SERVER_CONTEXT)
        self.assertIn("Factorio 2.1.12", handoff.context)
        self.assertIn("Space Age", handoff.context)
        self.assertIn("Elevated Rails", handoff.context)
        self.assertIn("Quality", handoff.context)
        self.assertIn("openai/gpt-oss-120b", handoff.context)
        self.assertIn("Never identify it as GPT-4", handoff.context)
        self.assertIn("No fresh live-game snapshot", handoff.context)

    def test_recognized_live_questions_select_fixed_snapshot(self) -> None:
        cases = (("Who is online?", "players"), ("What are we researching?", "research"),
                 ("How long has the save run?", "game_time"),
                 ("What surfaces are available?", "surfaces"))
        for request, query in cases:
            with self.subTest(request=request):
                handoff = self.router.route(decision(request=request))
                assert handoff is not None
                self.assertEqual(handoff.plan.route, RouteKind.DIRECT_LIVE_QUERY)
                self.assertEqual(handoff.plan.allowed_tool_families, ("fixed_live_snapshot",))
                self.assertEqual(handoff.live_query, query)

    def test_unrecognized_state_question_stays_conversation_without_tool(self) -> None:
        handoff = self.router.route(decision(request="How many iron plates are in that chest?"))
        assert handoff is not None
        self.assertEqual(handoff.plan.route, RouteKind.CONVERSATION)
        self.assertEqual(handoff.plan.allowed_tool_families, ())

    def test_action_shaped_request_still_receives_no_tool(self) -> None:
        handoff = self.router.route(decision(actor="dlbattle", request="Place this"))

        assert handoff is not None
        self.assertTrue(handoff.plan.authority.is_management)
        self.assertEqual(handoff.plan.allowed_tool_families, ())


if __name__ == "__main__":
    unittest.main()
