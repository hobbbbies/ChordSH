"""Tests for core/events.py"""
import pytest
from core.events import GameEvent, EventType


class TestEventType:
    def test_event_types_exist(self):
        assert EventType.GAME_STARTED
        assert EventType.GAME_ENDED
        assert EventType.NEW_TARGET_NOTE
        assert EventType.NOTE_DETECTED
        assert EventType.NOTE_CORRECT
        assert EventType.NOTE_INCORRECT
        assert EventType.STREAMING_STARTED
        assert EventType.STREAMING_STOPPED
        assert EventType.MESSAGE
        assert EventType.DEBUG
        assert EventType.ERROR


class TestGameEvent:
    def test_create_basic_event(self):
        event = GameEvent(EventType.GAME_STARTED)
        
        assert event.type == EventType.GAME_STARTED
        assert event.data is None

    def test_create_event_with_data(self):
        event = GameEvent(EventType.NOTE_CORRECT, {"played": "C", "expected": "C"})
        
        assert event.type == EventType.NOTE_CORRECT
        assert event.data == {"played": "C", "expected": "C"}

    def test_new_target_factory(self):
        event = GameEvent.new_target("G")
        
        assert event.type == EventType.NEW_TARGET_NOTE
        assert event.data == {"interval": "", "note": "G"}

    def test_note_detected_factory(self):
        event = GameEvent.note_detected("A", 440.0, None)
        
        assert event.type == EventType.NOTE_DETECTED
        assert event.data == {"note": "A", "freq": 440.0, "chord_name": None}

    def test_message_factory(self):
        event = GameEvent.message("Hello", row=2)
        
        assert event.type == EventType.MESSAGE
        assert event.data == {"text": "Hello", "row": 2}

    def test_message_factory_default_row(self):
        event = GameEvent.message("Test")
        
        assert event.data["row"] == 0

    def test_error_factory(self):
        event = GameEvent.error("Something went wrong")
        
        assert event.type == EventType.ERROR
        assert event.data == {"text": "Something went wrong"}

    def test_config_setup_factory(self):
        event = GameEvent.config_setup()
        
        assert event.type == EventType.CONFIG_SETUP
        assert event.data == {"scales": ["C Major", "G Major"]}
