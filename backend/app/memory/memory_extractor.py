import re
from typing import Optional, Dict, Any, List
from app.models.memory import MemoryType

class ExtractedMemory:
    def __init__(
        self,
        title: str,
        content: str,
        memory_type: MemoryType,
        category: str = "general",
        importance: int = 3,
        tags: Optional[List[str]] = None,
        structured_data: Optional[Dict[str, Any]] = None
    ):
        self.title = title
        self.content = content
        self.memory_type = memory_type
        self.category = category
        self.importance = importance
        self.tags = tags or []
        self.structured_data = structured_data or {}

class MemoryExtractor:
    """Deterministic, rule-based extraction engine for converting chat text into structured memories."""

    # Phase 9: `parse_reminder`/`parse_event` are exposed as standalone
    # static methods (not inlined into extract_from_text like rules 1-4
    # originally were) specifically so ReminderSkill/CalendarSkill (see
    # app/skills/reminder_skill.py, app/skills/calendar_skill.py) can reuse
    # the *exact same* parsing to build their confirmation text as the rule
    # below uses to persist the memory - one regex definition, not two
    # copies that could quietly drift apart.
    @staticmethod
    def parse_reminder(text: str) -> Optional[Dict[str, Any]]:
        """"remind me to <task> [at/by/on <when>]" -> {"task": ..., "due_date": ... | None}"""
        match = re.search(r"remind me to ([^\.\!\?]+)", text, re.IGNORECASE)
        if not match:
            return None
        task_text = match.group(1).strip()
        due_match = re.search(r"\s+\b(?:at|by|on)\b\s+([^\.\!\?]+)$", task_text, re.IGNORECASE)
        due_date = None
        if due_match:
            due_date = due_match.group(1).strip()
            task_text = task_text[: due_match.start()].strip()
        if not task_text:
            return None
        return {"task": task_text, "due_date": due_date}

    @staticmethod
    def parse_event(text: str) -> Optional[Dict[str, Any]]:
        """Explicit calendar-add lead-ins only ("add an event: ...",
        "schedule an event: ...", "put ... on my calendar", "add ... to my
        calendar") - deliberately NOT a bare "schedule X" trigger, since
        that would false-positive on plain questions like "what's my
        schedule tomorrow?" which aren't a request to add anything."""
        for pattern in (
            r"\badd (?:an )?event[:\s]+([^\.\!\?]+)",
            r"\bschedule an event[:\s]+([^\.\!\?]+)",
            r"\bput ([^\.\!\?]+?) on my calendar",
            r"\badd ([^\.\!\?]+?) to my calendar",
        ):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                event_text = match.group(1).strip()
                when_match = re.search(r"\s+\b(?:on|for|at)\b\s+([^\.\!\?]+)$", event_text, re.IGNORECASE)
                when = None
                if when_match:
                    when = when_match.group(1).strip()
                    event_text = event_text[: when_match.start()].strip()
                if not event_text:
                    return None
                return {"event": event_text, "date": when}
        return None

    @staticmethod
    def extract_from_text(text: str) -> List[ExtractedMemory]:
        extracted = []
        clean_text = text.strip()

        # 1. Preferences Rule: "My favorite [x] is [y]" or "I prefer [x] over [y]" or "I love/like [x]"
        pref_match = re.search(r"my favorite (\w+) is ([^\.\!\?]+)", clean_text, re.IGNORECASE)
        if pref_match:
            item_type, val = pref_match.group(1), pref_match.group(2).strip()
            extracted.append(ExtractedMemory(
                title=f"Favorite {item_type.capitalize()}: {val}",
                content=clean_text,
                memory_type=MemoryType.PREFERENCE,
                category="preferences",
                importance=4,
                tags=["preference", item_type.lower()],
                structured_data={"preference_type": item_type.lower(), "value": val}
            ))

        # 2. Events & Classes Rule: "My next class is [x] on/at [y]" or "Class [x] at [y]"
        class_match = re.search(r"my next class is ([^\.\!\?]+) (tomorrow|today|at|on) ([^\.\!\?]+)", clean_text, re.IGNORECASE)
        if class_match:
            subject = class_match.group(1).strip()
            time_info = f"{class_match.group(2)} {class_match.group(3)}".strip()
            extracted.append(ExtractedMemory(
                title=f"Class: {subject}",
                content=clean_text,
                memory_type=MemoryType.CLASS,
                category="academics",
                importance=4,
                tags=["class", subject.lower()],
                structured_data={"subject": subject, "schedule": time_info}
            ))
        elif re.search(r"\bclass\b", clean_text, re.IGNORECASE) and re.search(r"\b(tomorrow|at|on|pm|am)\b", clean_text, re.IGNORECASE):
            extracted.append(ExtractedMemory(
                title="Class Schedule Note",
                content=clean_text,
                memory_type=MemoryType.CLASS,
                category="academics",
                importance=3,
                tags=["class"]
            ))

        # 3. Tasks Rule: "I have to [x] by [y]" or "Todo: [x]" or "Need to [x]"
        task_match = re.search(r"i have to ([^\.\!\?]+) by ([^\.\!\?]+)", clean_text, re.IGNORECASE)
        if task_match:
            task_name, due_date = task_match.group(1).strip(), task_match.group(2).strip()
            extracted.append(ExtractedMemory(
                title=f"Task: {task_name}",
                content=clean_text,
                memory_type=MemoryType.TASK,
                category="tasks",
                importance=4,
                tags=["task", "todo"],
                structured_data={"task": task_name, "due_date": due_date}
            ))
        elif clean_text.lower().startswith("todo:") or clean_text.lower().startswith("task:"):
            task_name = clean_text.split(":", 1)[1].strip()
            extracted.append(ExtractedMemory(
                title=f"Task: {task_name}",
                content=clean_text,
                memory_type=MemoryType.TASK,
                category="tasks",
                importance=3,
                tags=["task"]
            ))

        # 4. Notes Rule: "Note: [x]" or "Remember that [x]"
        if clean_text.lower().startswith("note:") or re.search(r"remember that ([^\.\!\?]+)", clean_text, re.IGNORECASE):
            extracted.append(ExtractedMemory(
                title="User Note",
                content=clean_text,
                memory_type=MemoryType.NOTE,
                category="notes",
                importance=3,
                tags=["note"]
            ))

        # 5. Reminders Rule (Phase 9): "Remind me to [x] [at/by/on [y]]" -
        # a real, previously-unhandled gap: pre-Phase-9, "Remind me to
        # submit the report" classified as IntentType.TASK (see
        # app/intent/intent_service.py) but nothing ever actually
        # persisted it - the LLM would free-respond with no memory created
        # and no record of the ask. See app/skills/reminder_skill.py for
        # the matching user-facing confirmation.
        reminder = MemoryExtractor.parse_reminder(clean_text)
        if reminder:
            extracted.append(ExtractedMemory(
                title=f"Reminder: {reminder['task']}",
                content=clean_text,
                memory_type=MemoryType.TASK,
                category="tasks",
                importance=4,
                tags=["task", "reminder"],
                structured_data=(
                    {"task": reminder["task"], "due_date": reminder["due_date"]}
                    if reminder["due_date"] else {"task": reminder["task"]}
                ),
            ))

        # 6. Calendar Events Rule (Phase 9): explicit "add an event: [x]",
        # "schedule an event: [x]", "put [x] on my calendar", "add [x] to
        # my calendar" - see app/skills/calendar_skill.py for the matching
        # confirmation. Deliberately narrow lead-ins (see parse_event's
        # docstring) rather than a bare "schedule X", to avoid
        # false-positives on questions like "what's my schedule tomorrow?".
        event = MemoryExtractor.parse_event(clean_text)
        if event:
            extracted.append(ExtractedMemory(
                title=f"Event: {event['event']}",
                content=clean_text,
                memory_type=MemoryType.EVENT,
                category="events",
                importance=3,
                tags=["event"],
                structured_data=(
                    {"event": event["event"], "date": event["date"]}
                    if event["date"] else {"event": event["event"]}
                ),
            ))

        return extracted
