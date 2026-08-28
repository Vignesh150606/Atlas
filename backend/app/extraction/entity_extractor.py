import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from app.models.entity import EntityType

try:
    from dateutil import parser as dateutil_parser
except ImportError:  # pragma: no cover - defensive; see requirements.txt
    dateutil_parser = None


@dataclass
class ExtractedEntity:
    entity_type: EntityType
    name: str
    details: Dict[str, Any] = field(default_factory=dict)
    confidence: int = 70


# --- People -----------------------------------------------------------
# Two-capitalized-word sequences, optionally with a title prefix. This is a
# blunt heuristic (real NER needs a model), so it's deliberately
# conservative: a denylist filters out common two-word capitalized phrases
# that aren't names, to keep false positives down rather than trying to be
# exhaustive.
_NAME_RE = re.compile(r"\b(?:(Dr|Mr|Mrs|Ms|Prof)\.\s+)?([A-Z][a-z]+)\s([A-Z][a-z]+)\b")
_NAME_DENYLIST = {
    "new york", "los angeles", "san francisco", "united states", "north america",
    "south america", "united kingdom", "new jersey", "las vegas", "hong kong",
    "san diego", "new delhi", "next week", "next month", "this week", "this month",
}

# --- Companies ----------------------------------------------------------
_COMPANY_SUFFIX_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&]+(?:\s[A-Z][A-Za-z0-9&]+){0,3})\s(Inc\.?|Corp\.?|LLC|Ltd\.?|Co\.|Technologies|Systems)\b"
)
_COMPANY_CONTEXT_RE = re.compile(
    r"\b(?:works? at|working at|intern(?:ship)? at|employed (?:at|by)|joins?|hired by)\s+([A-Z][A-Za-z0-9&]+(?:\s[A-Z][A-Za-z0-9&]+){0,3})\b"
)

# --- Courses --------------------------------------------------------------
_COURSE_RE = re.compile(r"\b([A-Z]{2,5})[\s-](\d{2,4}[A-Z]?)\b")

# --- Tasks ------------------------------------------------------------
_TASK_LINE_RE = re.compile(r"^\s*(?:TODO|Task)[:\-]\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_TASK_PHRASE_RE = re.compile(r"\b(?:need to|have to|must)\s+([^.!?\n]+)", re.IGNORECASE)

# --- Deadlines --------------------------------------------------------
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_MONTH_DATE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b",
    re.IGNORECASE,
)
_SLASH_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_DEADLINE_CONTEXT_RE = re.compile(
    r"\b(due|deadline|by|submit(?:ted)? by|due date)\b[:\s]*([^.!?\n]{0,60})", re.IGNORECASE
)

# --- Skills -------------------------------------------------------------
# Non-exhaustive curated list spanning common technical + professional
# skills. Matched case-insensitively as whole phrases against document
# text - a keyword list, not a trained classifier.
_SKILL_KEYWORDS = [
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust", "Kotlin", "Swift",
    "SQL", "NoSQL", "React", "Angular", "Vue", "Node.js", "Django", "Flask", "FastAPI", "Spring",
    "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git", "Linux", "Machine Learning",
    "Deep Learning", "Data Analysis", "Data Science", "Public Speaking", "Project Management",
    "Leadership", "Communication", "Teamwork", "Problem Solving", "Agile", "Scrum",
    "UI/UX Design", "Figma", "Photoshop", "Excel", "PowerPoint", "Statistics",
    "Natural Language Processing", "Computer Vision", "REST APIs", "GraphQL",
    "CI/CD", "Testing", "Debugging", "Algorithms", "Data Structures",
]
_SKILL_RE = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in _SKILL_KEYWORDS) + r")\b", re.IGNORECASE
)


def _dedupe(entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
    seen = set()
    unique = []
    for e in entities:
        key = (e.entity_type, e.name.strip().lower())
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def _best_effort_parse_date(raw_text: str) -> Optional[str]:
    if dateutil_parser is None:
        return None
    try:
        parsed = dateutil_parser.parse(raw_text, fuzzy=True, default=None)
        return parsed.date().isoformat()
    except Exception:
        return None


class EntityExtractor:
    """Deterministic, rule-based entity extraction over imported document
    text - same philosophy as MemoryExtractor (app/memory/memory_extractor.py):
    regex/keyword rules, no ML/embeddings, documented as heuristic rather
    than pretending to be precise NER.
    """

    @staticmethod
    def _extract_people(text: str) -> List[ExtractedEntity]:
        results = []
        for m in _NAME_RE.finditer(text):
            title, first, last = m.group(1), m.group(2), m.group(3)
            full = f"{first} {last}"
            if full.lower() in _NAME_DENYLIST:
                continue
            display = f"{title}. {full}" if title else full
            results.append(ExtractedEntity(EntityType.PERSON, display, confidence=55))
        return results

    @staticmethod
    def _extract_companies(text: str) -> List[ExtractedEntity]:
        results = []
        for m in _COMPANY_SUFFIX_RE.finditer(text):
            name = f"{m.group(1)} {m.group(2)}".strip()
            results.append(ExtractedEntity(EntityType.COMPANY, name, confidence=75))
        for m in _COMPANY_CONTEXT_RE.finditer(text):
            results.append(ExtractedEntity(EntityType.COMPANY, m.group(1).strip(), confidence=60))
        return results

    @staticmethod
    def _extract_courses(text: str) -> List[ExtractedEntity]:
        results = []
        for m in _COURSE_RE.finditer(text):
            code = f"{m.group(1)} {m.group(2)}"
            results.append(ExtractedEntity(EntityType.COURSE, code, confidence=65))
        return results

    @staticmethod
    def _extract_topics(structured_data: Dict[str, Any]) -> List[ExtractedEntity]:
        results = []
        headings = (structured_data or {}).get("headings", [])
        for h in headings:
            heading_text = h.get("text") if isinstance(h, dict) else None
            if heading_text:
                results.append(ExtractedEntity(EntityType.TOPIC, heading_text.strip(), confidence=70))
        return results

    @staticmethod
    def _extract_tasks(text: str, structured_data: Dict[str, Any]) -> List[ExtractedEntity]:
        results = []
        for item in (structured_data or {}).get("checklist_items", []):
            if isinstance(item, dict) and not item.get("done") and item.get("text"):
                results.append(ExtractedEntity(
                    EntityType.TASK, item["text"].strip(), details={"source": "checklist"}, confidence=85
                ))
        for m in _TASK_LINE_RE.finditer(text):
            results.append(ExtractedEntity(EntityType.TASK, m.group(1).strip(), confidence=75))
        for m in _TASK_PHRASE_RE.finditer(text):
            phrase = m.group(1).strip()
            if 3 <= len(phrase) <= 120:
                results.append(ExtractedEntity(EntityType.TASK, phrase, confidence=55))
        return results

    @staticmethod
    def _extract_deadlines(text: str) -> List[ExtractedEntity]:
        results = []
        date_matches = list(_ISO_DATE_RE.finditer(text)) + list(_MONTH_DATE_RE.finditer(text)) + list(_SLASH_DATE_RE.finditer(text))
        for m in date_matches:
            raw = m.group(0)
            parsed = _best_effort_parse_date(raw)
            results.append(ExtractedEntity(
                EntityType.DEADLINE, raw,
                details={"raw_text": raw, "parsed_date": parsed},
                confidence=60 if parsed else 40,
            ))
        # Higher-confidence variant: a date near an explicit "due"/"deadline"/"by" cue.
        for m in _DEADLINE_CONTEXT_RE.finditer(text):
            snippet = m.group(2).strip()
            if not snippet:
                continue
            parsed = _best_effort_parse_date(snippet)
            if parsed:
                results.append(ExtractedEntity(
                    EntityType.DEADLINE, snippet,
                    details={"raw_text": snippet, "parsed_date": parsed, "cue": m.group(1)},
                    confidence=80,
                ))
        return results

    @staticmethod
    def _extract_skills(text: str) -> List[ExtractedEntity]:
        results = []
        for m in _SKILL_RE.finditer(text):
            # Normalize to the canonical casing from the keyword list rather
            # than whatever casing appeared in the source text.
            matched_lower = m.group(1).lower()
            canonical = next((s for s in _SKILL_KEYWORDS if s.lower() == matched_lower), m.group(1))
            results.append(ExtractedEntity(EntityType.SKILL, canonical, confidence=80))
        return results

    @classmethod
    def extract(cls, text: str, structured_data: Optional[Dict[str, Any]] = None) -> List[ExtractedEntity]:
        """Projects get no dedicated regex rule (no reliable text pattern
        distinguishes "a project name" from any other capitalized phrase);
        instead PROJECT entities come from an explicit "Project:" line or
        markdown heading containing the word "project", handled inline here
        rather than as a separate always-on rule that would be too noisy.
        """
        structured_data = structured_data or {}
        results: List[ExtractedEntity] = []

        results.extend(cls._extract_people(text))
        results.extend(cls._extract_companies(text))
        results.extend(cls._extract_courses(text))
        results.extend(cls._extract_topics(structured_data))
        results.extend(cls._extract_tasks(text, structured_data))
        results.extend(cls._extract_deadlines(text))
        results.extend(cls._extract_skills(text))

        for m in re.finditer(r"^\s*Project[:\-]\s*(.+)$", text, re.IGNORECASE | re.MULTILINE):
            results.append(ExtractedEntity(EntityType.PROJECT, m.group(1).strip(), confidence=80))
        for h in structured_data.get("headings", []):
            heading_text = h.get("text") if isinstance(h, dict) else None
            if heading_text and "project" in heading_text.lower():
                results.append(ExtractedEntity(EntityType.PROJECT, heading_text.strip(), confidence=65))

        return _dedupe(results)
