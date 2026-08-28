import pytest
from app.planner.planner import Planner
from app.intent.intent_service import IntentService


def _plan_for(message: str):
    intent_result = IntentService.classify(message)
    return Planner.build_plan(message, intent_result)


def _single_call(message: str):
    plan = _plan_for(message)
    assert len(plan.tool_calls) == 1, f"expected exactly one tool call for {message!r}, got {plan.tool_calls}"
    return plan.tool_calls[0]


def test_open_app_routes_to_launch_app():
    call = _single_call("Open WhatsApp")
    assert call.tool == "launch_app"
    assert call.args == {"app_name": "WhatsApp"}


def test_launch_app_verb_also_routes_to_launch_app():
    call = _single_call("launch Spotify")
    assert call.tool == "launch_app"
    assert call.args["app_name"] == "Spotify"


def test_device_action_plan_skips_memory_and_knowledge_retrieval():
    plan = _plan_for("Open WhatsApp")
    assert plan.needs_memory_retrieval is False
    assert plan.needs_knowledge_retrieval is False


def test_open_maps_to_does_not_launch_an_app_named_maps():
    call = _single_call("navigate to the airport")
    assert call.tool == "intent_action"
    assert call.args == {"action": "maps", "query": "the airport"}


def test_open_contacts_routes_to_intent_not_app_launch():
    call = _single_call("open my contacts")
    assert call.tool == "intent_action"
    assert call.args == {"action": "contacts"}


def test_open_notifications_routes_to_accessibility_not_notification_tool():
    call = _single_call("open the notification shade")
    assert call.tool == "accessibility"
    assert call.args == {"action": "open_notifications"}


def test_open_url_routes_to_intent_action():
    call = _single_call("open example.com")
    assert call.tool == "intent_action"
    assert call.args["action"] == "open_url"
    assert "example.com" in call.args["url"]


def test_call_someone_routes_to_dial():
    call = _single_call("call 555-1234")
    assert call.tool == "intent_action"
    assert call.args == {"action": "dial", "number": "555-1234"}


def test_email_routes_to_intent_action():
    call = _single_call("email John about the report")
    assert call.tool == "intent_action"
    assert call.args["action"] == "email"
    assert call.args["to"] == "John about the report"


def test_go_back_routes_to_accessibility_back():
    call = _single_call("go back")
    assert call.tool == "accessibility"
    assert call.args == {"action": "back"}


def test_go_home_routes_to_accessibility_home():
    call = _single_call("go home")
    assert call.tool == "accessibility"
    assert call.args == {"action": "home"}


def test_recent_apps_routes_to_accessibility_recents():
    call = _single_call("show recents")
    assert call.tool == "accessibility"
    assert call.args == {"action": "recents"}


def test_read_screen_routes_to_accessibility():
    call = _single_call("what's on my screen")
    assert call.tool == "accessibility"
    assert call.args == {"action": "read_screen"}


@pytest.mark.parametrize(
    "message,expected_action",
    [
        ("play some music", "play"),
        ("pause", "pause"),
        ("skip", "next"),
        ("go back a track", "previous"),
        ("volume up", "volume_up"),
        ("turn the volume down", "volume_down"),
        ("what's playing", "now_playing"),
    ],
)
def test_media_phrases_route_to_media_tool(message, expected_action):
    call = _single_call(message)
    assert call.tool == "media"
    assert call.args == {"action": expected_action}


def test_check_notifications_routes_to_notifications_tool():
    call = _single_call("check my notifications")
    assert call.tool == "notifications"
    assert call.args == {"action": "summarize"}


def test_copy_to_clipboard_routes_to_clipboard_write():
    call = _single_call("copy this address to clipboard")
    assert call.tool == "clipboard"
    assert call.args == {"action": "write", "text": "this address"}


def test_whats_in_clipboard_routes_to_clipboard_read():
    call = _single_call("what's in my clipboard")
    assert call.tool == "clipboard"
    assert call.args == {"action": "read"}


def test_ordinary_question_does_not_trigger_a_device_action():
    plan = _plan_for("What is the capital of France?")
    tool_names = [c.tool for c in plan.tool_calls]
    assert "launch_app" not in tool_names
    assert "accessibility" not in tool_names


def test_ordinary_greeting_does_not_trigger_a_device_action():
    plan = _plan_for("Hello there!")
    assert plan.tool_calls == []


def test_existing_calculation_plan_is_unaffected_by_device_routing():
    plan = _plan_for("What is 12 * 7?")
    tool_names = [c.tool for c in plan.tool_calls]
    assert "calculator" in tool_names
    assert plan.needs_memory_retrieval  # unaffected: QUESTION intent still needs retrieval
