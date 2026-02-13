import pytest
from app.services.intelligence import IntelligenceService

def test_detect_intent_planning():
    service = IntelligenceService()
    intent = service.detect_intent("Can you make a plan for my project?")
    assert intent == "planning"

def test_detect_intent_coding():
    service = IntelligenceService()
    intent = service.detect_intent("Write a python function to scrape a website")
    assert intent == "coding"

def test_detect_intent_general():
    service = IntelligenceService()
    intent = service.detect_intent("Hello, how are you?")
    assert intent == "general"

def test_find_fuzzy_match_exact():
    service = IntelligenceService()
    match = service.find_fuzzy_match("search", ["search", "read_pdf", "ocr"])
    assert match == "search"

def test_find_fuzzy_match_typo():
    service = IntelligenceService()
    match = service.find_fuzzy_match("seaarch", ["search", "read_pdf", "ocr"])
    assert match == "search"

def test_find_fuzzy_match_no_match():
    service = IntelligenceService()
    # Using a very low threshold (implicit 0.7)
    match = service.find_fuzzy_match("completely_different", ["search", "read_pdf", "ocr"])
    assert match is None
