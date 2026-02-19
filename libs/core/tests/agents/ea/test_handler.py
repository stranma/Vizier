"""Tests for EA message handler (Telegram bridge)."""

from __future__ import annotations

from vizier.core.agents.ea.capability_summary import ProjectCapability, build_capability
from vizier.core.agents.ea.handler import EAHandler

from ...runtime.mock_anthropic import make_mock_client, make_text_response


class TestEAHandler:
    def test_handle_message_returns_text(self) -> None:
        client = make_mock_client(make_text_response("I'll handle that for you."))
        handler = EAHandler(client=client)
        response = handler.handle_message("Build auth for project-alpha")
        assert response == "I'll handle that for you."

    def test_handle_message_fresh_runtime(self) -> None:
        client = make_mock_client(
            make_text_response("First response"),
            make_text_response("Second response"),
        )
        handler = EAHandler(client=client)
        r1 = handler.handle_message("First task")
        r2 = handler.handle_message("Second task")
        assert r1 == "First response"
        assert r2 == "Second response"
        assert client.messages.create.call_count == 2

    def test_handle_message_uses_jit_assembly(self) -> None:
        client = make_mock_client(make_text_response("Status report"))
        handler = EAHandler(client=client)
        handler.handle_message("/status")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "Status Report Context" in call_kwargs["system"]

    def test_handle_message_error_graceful(self) -> None:
        client = make_mock_client()
        client.messages.create.side_effect = RuntimeError("API error")
        handler = EAHandler(client=client)
        response = handler.handle_message("test")
        assert "error" in response.lower() or "occurred" in response.lower()

    def test_update_capabilities(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        handler = EAHandler(client=client)
        caps = [build_capability(name="alpha", plugin="software")]
        handler.update_capabilities(caps)
        handler.handle_message("Build something")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "alpha" in call_kwargs["system"]

    def test_update_priorities(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        handler = EAHandler(client=client)
        handler.update_priorities("1. Ship by Friday")
        handler.handle_message("What should I do?")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "Ship by Friday" in call_kwargs["system"]

    def test_capabilities_text_property(self) -> None:
        handler = EAHandler(client=make_mock_client())
        assert handler.capabilities_text == "No projects registered."
        handler.update_capabilities([ProjectCapability(name="alpha")])
        assert "alpha" in handler.capabilities_text

    def test_send_callback_passed_to_tools(self) -> None:
        sent: list[str] = []
        client = make_mock_client(make_text_response("Done"))
        handler = EAHandler(client=client, send_callback=sent.append)
        handler.handle_message("test")
        call_kwargs = client.messages.create.call_args.kwargs
        tool_names = {t["name"] for t in call_kwargs.get("tools", [])}
        assert "send_briefing" in tool_names

    def test_custom_model(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        handler = EAHandler(client=client, model="custom-model")
        handler.handle_message("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "custom-model"
