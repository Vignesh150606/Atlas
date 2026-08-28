import pytest
from app.memory.memory_extractor import MemoryExtractor
from app.models.memory import MemoryType

def test_memory_extractor_preference():
    text = "My favorite color is sapphire blue."
    results = MemoryExtractor.extract_from_text(text)
    assert len(results) == 1
    assert results[0].memory_type == MemoryType.PREFERENCE
    assert "Favorite Color" in results[0].title
    assert results[0].structured_data["value"] == "sapphire blue"

def test_memory_extractor_task():
    text = "I have to finish my project by Friday."
    results = MemoryExtractor.extract_from_text(text)
    assert len(results) == 1
    assert results[0].memory_type == MemoryType.TASK
    assert "finish my project" in results[0].title
    assert results[0].structured_data["due_date"] == "Friday"

def test_memory_extractor_class():
    text = "My next class is AI tomorrow at 9."
    results = MemoryExtractor.extract_from_text(text)
    assert len(results) == 1
    assert results[0].memory_type == MemoryType.CLASS
    assert "AI" in results[0].title
