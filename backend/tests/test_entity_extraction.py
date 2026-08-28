from app.extraction.entity_extractor import EntityExtractor
from app.models.entity import EntityType


def _names(entities, entity_type):
    return [e.name for e in entities if e.entity_type == entity_type]


def test_extracts_people_with_denylist_filtering():
    text = "Meeting notes with Dr. John Smith about the roadmap. Held in New York this time."
    entities = EntityExtractor.extract(text)
    people = _names(entities, EntityType.PERSON)
    assert any("John Smith" in name for name in people)
    # "New York" is a denylisted non-name phrase and must not show up as a person
    assert not any("New York" in name for name in people)


def test_extracts_companies_by_suffix_and_context():
    text = "I just joined Acme Corp. as an engineer. Also interviewing at Globex Inc."
    entities = EntityExtractor.extract(text)
    companies = _names(entities, EntityType.COMPANY)
    assert any("Acme Corp" in c for c in companies)


def test_extracts_courses_by_code_pattern():
    text = "Registered for CS 101 and MATH-301 this semester."
    entities = EntityExtractor.extract(text)
    courses = _names(entities, EntityType.COURSE)
    assert "CS 101" in courses
    assert "MATH 301" in courses


def test_extracts_topics_from_markdown_headings():
    structured_data = {"headings": [{"level": 1, "text": "Distributed Systems"}]}
    entities = EntityExtractor.extract("Some content about distributed systems.", structured_data)
    topics = _names(entities, EntityType.TOPIC)
    assert "Distributed Systems" in topics


def test_extracts_tasks_from_checklist_and_todo_lines():
    structured_data = {"checklist_items": [{"done": False, "text": "Write final report"}]}
    text = "TODO: email the professor\nAlready done stuff here."
    entities = EntityExtractor.extract(text, structured_data)
    tasks = _names(entities, EntityType.TASK)
    assert "Write final report" in tasks
    assert "email the professor" in tasks


def test_completed_checklist_items_are_not_extracted_as_open_tasks():
    structured_data = {"checklist_items": [{"done": True, "text": "Already finished task"}]}
    entities = EntityExtractor.extract("irrelevant body text", structured_data)
    tasks = _names(entities, EntityType.TASK)
    assert "Already finished task" not in tasks


def test_extracts_deadlines_with_best_effort_date_parsing():
    text = "The project is due 2026-09-15. Also submit the form by Sept 20, 2026."
    entities = EntityExtractor.extract(text)
    deadlines = [e for e in entities if e.entity_type == EntityType.DEADLINE]
    assert len(deadlines) > 0
    parsed_dates = [d.details.get("parsed_date") for d in deadlines]
    assert "2026-09-15" in parsed_dates


def test_extracts_skills_from_curated_keyword_list():
    text = "Proficient in Python, Docker, and Machine Learning. Also strong at Public Speaking."
    entities = EntityExtractor.extract(text)
    skills = _names(entities, EntityType.SKILL)
    assert "Python" in skills
    assert "Docker" in skills
    assert "Machine Learning" in skills


def test_extracts_projects_from_explicit_project_line():
    text = "Project: Atlas Mobile App\n\nThis project focuses on the Android client."
    entities = EntityExtractor.extract(text)
    projects = _names(entities, EntityType.PROJECT)
    assert "Atlas Mobile App" in projects


def test_extraction_deduplicates_repeated_mentions():
    text = "Python is great. I love Python. Python Python Python."
    entities = EntityExtractor.extract(text)
    skills = [e for e in entities if e.entity_type == EntityType.SKILL and e.name == "Python"]
    assert len(skills) == 1


def test_extraction_handles_empty_text_gracefully():
    entities = EntityExtractor.extract("", {})
    assert entities == []
