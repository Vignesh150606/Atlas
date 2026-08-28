import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("atlas.trace")


@dataclass
class RequestTrace:
    """One structured record per chat turn, covering every stage of the
    cognitive pipeline. Logged as a single JSON line so it's easy to grep/
    ingest, without ever including raw message content - only shapes,
    counts, and identifiers (see to_dict's redaction).
    """
    conversation_id: Optional[int] = None
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    planner_notes: Optional[str] = None
    tools_selected: List[str] = field(default_factory=list)
    tools_succeeded: List[str] = field(default_factory=list)
    tools_failed: List[str] = field(default_factory=list)
    retrieved_memory_count: int = 0
    retrieved_memory_ids: List[str] = field(default_factory=list)
    retrieved_document_count: int = 0
    retrieved_document_ids: List[str] = field(default_factory=list)
    provider: Optional[str] = None
    latency_ms: Optional[float] = None
    memory_updates: int = 0  # count of memories created/updated this turn
    device_action: Optional[str] = None  # Phase 8: tool name if this turn produced a device_action, else None
    follow_up_detected: bool = False  # Phase 9: ConversationIntelligenceService.detect_follow_up fired
    ambiguity_detected: bool = False  # Phase 9: ConversationIntelligenceService.detect_ambiguous_command fired
    error: Optional[str] = None

    _start_time: float = field(default_factory=time.monotonic, repr=False)

    def mark_complete(self) -> None:
        self.latency_ms = round((time.monotonic() - self._start_time) * 1000, 2)

    def to_dict(self) -> Dict[str, Any]:
        """No sensitive data: message content, memory content/titles, and
        tool arguments are intentionally excluded - only counts, ids, and
        classification labels are recorded.
        """
        d = asdict(self)
        d.pop("_start_time", None)
        return d

    def log(self) -> None:
        self.mark_complete()
        logger.info(json.dumps(self.to_dict(), default=str))
