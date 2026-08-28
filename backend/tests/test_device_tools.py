import pytest
from app.tools.device_tools import (
    LaunchAppTool,
    AppSearchTool,
    AccessibilityActionTool,
    NotificationTool,
    MediaControlTool,
    ClipboardTool,
    IntentActionTool,
    DEVICE_TOOL_NAMES,
)


@pytest.mark.asyncio
async def test_launch_app_tool_produces_directive():
    result = await LaunchAppTool().run(app_name="WhatsApp")
    assert result.success
    assert result.device_action == {
        "module": "app_manager",
        "action": "launch_app",
        "args": {"query": "WhatsApp"},
    }


@pytest.mark.asyncio
async def test_launch_app_tool_rejects_empty_name():
    result = await LaunchAppTool().run(app_name="   ")
    assert not result.success
    assert result.device_action is None


@pytest.mark.asyncio
async def test_launch_app_tool_does_not_require_confirmation():
    # Regression guard for Phase 9's requires_confirmation addition: this
    # must default to False so every pre-Phase-9 device action is unaffected.
    result = await LaunchAppTool().run(app_name="WhatsApp")
    assert result.requires_confirmation is False


@pytest.mark.asyncio
async def test_search_app_tool_produces_directive():
    result = await AppSearchTool().run(query="calc")
    assert result.success
    assert result.device_action["action"] == "search_app"
    assert result.device_action["args"] == {"query": "calc"}


@pytest.mark.asyncio
async def test_accessibility_click_requires_target():
    result = await AccessibilityActionTool().run(action="click")
    assert not result.success

    result_ok = await AccessibilityActionTool().run(action="click", target="Send button")
    assert result_ok.success
    assert result_ok.device_action == {
        "module": "accessibility",
        "action": "click",
        "args": {"target": "Send button"},
    }


@pytest.mark.asyncio
async def test_accessibility_type_text_requires_text():
    result = await AccessibilityActionTool().run(action="type_text", target="Search box")
    assert not result.success

    result_ok = await AccessibilityActionTool().run(action="type_text", target="Search box", text="pizza")
    assert result_ok.success
    assert result_ok.device_action["args"] == {"target": "Search box", "text": "pizza"}


@pytest.mark.asyncio
async def test_accessibility_global_actions_need_no_target():
    for action in ("back", "home", "recents", "open_notifications", "read_screen"):
        result = await AccessibilityActionTool().run(action=action)
        assert result.success, f"{action} should not require a target"
        assert result.device_action["action"] == action


@pytest.mark.asyncio
async def test_accessibility_rejects_unknown_action():
    result = await AccessibilityActionTool().run(action="teleport")
    assert not result.success
    assert "Unsupported accessibility action" in result.error


@pytest.mark.asyncio
async def test_accessibility_scroll_defaults_direction_down():
    result = await AccessibilityActionTool().run(action="scroll")
    assert result.success
    assert result.device_action["args"]["direction"] == "down"


@pytest.mark.asyncio
async def test_notification_tool_default_action_is_summarize():
    result = await NotificationTool().run()
    assert result.success
    assert result.device_action["action"] == "summarize"


@pytest.mark.asyncio
async def test_notification_tool_rejects_unknown_action():
    result = await NotificationTool().run(action="explode")
    assert not result.success


@pytest.mark.parametrize(
    "action",
    ["play", "pause", "next", "previous", "volume_up", "volume_down", "now_playing"],
)
@pytest.mark.asyncio
async def test_media_control_tool_all_valid_actions(action):
    result = await MediaControlTool().run(action=action)
    assert result.success
    assert result.device_action == {"module": "media_session", "action": action, "args": {}}


@pytest.mark.asyncio
async def test_media_control_tool_rejects_unknown_action():
    result = await MediaControlTool().run(action="shuffle")
    assert not result.success


@pytest.mark.asyncio
async def test_clipboard_write_requires_text():
    result = await ClipboardTool().run(action="write")
    assert not result.success

    result_ok = await ClipboardTool().run(action="write", text="hello world")
    assert result_ok.success
    assert result_ok.device_action["args"] == {"text": "hello world"}
    # Phase 9 / Security: writing silently overwrites whatever the user had
    # on their clipboard - the client should confirm before doing that.
    assert result_ok.requires_confirmation is True


@pytest.mark.asyncio
async def test_clipboard_read_needs_no_text():
    result = await ClipboardTool().run(action="read")
    assert result.success
    assert result.device_action["args"] == {}
    assert result.requires_confirmation is False


@pytest.mark.asyncio
async def test_intent_action_open_url():
    result = await IntentActionTool().run(action="open_url", url="https://example.com")
    assert result.success
    assert result.device_action["args"] == {"url": "https://example.com"}


@pytest.mark.asyncio
async def test_intent_action_dial_requires_number():
    result = await IntentActionTool().run(action="dial")
    assert not result.success

    result_ok = await IntentActionTool().run(action="dial", number="555-1234")
    assert result_ok.success
    assert result_ok.device_action["args"] == {"number": "555-1234"}
    # Phase 9 / Security: a misheard number shouldn't silently pre-fill the
    # dialer with zero confirmation cue, even though dial already stops
    # short of placing the call itself (see docs/Phase8_KnownLimitations.md).
    assert result_ok.requires_confirmation is True


@pytest.mark.asyncio
async def test_intent_action_open_url_does_not_require_confirmation():
    # Non-destructive intent actions (open_url, contacts, maps, share,
    # email) are unaffected by the Phase 9 confirmation flag - only `dial`
    # is flagged among intent_action's six actions.
    result = await IntentActionTool().run(action="open_url", url="https://example.com")
    assert result.requires_confirmation is False


@pytest.mark.asyncio
async def test_intent_action_contacts_needs_no_args():
    result = await IntentActionTool().run(action="contacts")
    assert result.success
    assert result.device_action["args"] == {}


@pytest.mark.asyncio
async def test_intent_action_maps_requires_query():
    result = await IntentActionTool().run(action="maps")
    assert not result.success

    result_ok = await IntentActionTool().run(action="maps", query="Golden Gate Bridge")
    assert result_ok.success


@pytest.mark.asyncio
async def test_intent_action_email_requires_to():
    result = await IntentActionTool().run(action="email", subject="Hi")
    assert not result.success

    result_ok = await IntentActionTool().run(action="email", to="a@b.com", subject="Hi", body="Hello")
    assert result_ok.success
    assert result_ok.device_action["args"] == {"to": "a@b.com", "subject": "Hi", "body": "Hello"}


@pytest.mark.asyncio
async def test_intent_action_rejects_unknown_action():
    result = await IntentActionTool().run(action="teleport")
    assert not result.success


def test_device_tool_names_matches_all_seven_tools():
    assert DEVICE_TOOL_NAMES == {
        "launch_app", "search_app", "accessibility",
        "notifications", "media", "clipboard", "intent_action",
    }
