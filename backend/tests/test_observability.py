import json
import logging
import pytest
from app.observability.trace import RequestTrace


def test_trace_to_dict_excludes_sensitive_fields():
    trace = RequestTrace(conversation_id=1, intent="question", provider="mock")
    d = trace.to_dict()
    assert "_start_time" not in d
    # No field name suggests raw message/memory content is ever stored
    assert not any("content" in key or "message_text" in key for key in d)


def test_trace_records_latency_on_mark_complete():
    trace = RequestTrace()
    trace.mark_complete()
    assert trace.latency_ms is not None
    assert trace.latency_ms >= 0


def test_trace_log_emits_valid_json(caplog):
    trace = RequestTrace(conversation_id=5, intent="task", provider="mock", retrieved_memory_count=2)
    with caplog.at_level(logging.INFO, logger="atlas.trace"):
        trace.log()
    assert len(caplog.records) == 1
    parsed = json.loads(caplog.records[0].message)
    assert parsed["conversation_id"] == 5
    assert parsed["intent"] == "task"
    assert parsed["retrieved_memory_count"] == 2


def test_trace_tools_lists_default_empty():
    trace = RequestTrace()
    assert trace.tools_selected == []
    assert trace.tools_succeeded == []
    assert trace.tools_failed == []
