"""
Game events that flow between engine and UI adapters.
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class EventType(Enum):
    """All possible game events."""
    # Game state
    GAME_STARTED = auto()
    GAME_ENDED = auto()
    
    # Note challenges
    NEW_TARGET_NOTE = auto()
    NOTE_DETECTED = auto()
    NOTE_CORRECT = auto()
    NOTE_INCORRECT = auto()
    
    # Recording state
    RECORDING_STARTED = auto()
    RECORDING_STOPPED = auto()
    STREAMING_STARTED = auto()
    STREAMING_STOPPED = auto()
    
    # Messages
    MESSAGE = auto()
    DEBUG = auto()
    ERROR = auto()

    # Countdown
    COUNTDOWN_STARTED = auto()
    COUNTDOWN_FINISHED = auto()
    CONFIG_SETUP = auto()


@dataclass
class GameEvent:
    """
    Immutable event passed from engine to UI.
    
    Attributes:
        type: The event type
        data: Event-specific payload (note, message, etc.)
    """
    type: EventType
    data: dict[str, Any] | None = None
    
    # Convenience constructors
    @classmethod
    def new_target(cls, note: str, interval: str = "") -> "GameEvent":
        return cls(EventType.NEW_TARGET_NOTE, {"note": note, "interval": interval})
    
    @classmethod
    def note_detected(cls, note: str, freq: float, chord_name: str | None = None) -> "GameEvent":
        return cls(EventType.NOTE_DETECTED, {"note": note, "freq": freq, "chord_name": chord_name})
    
    @classmethod
    def message(cls, text: str, row: int = 0) -> "GameEvent":
        return cls(EventType.MESSAGE, {"text": text, "row": row})
    
    @classmethod
    def error(cls, text: str) -> "GameEvent":
        return cls(EventType.ERROR, {"text": text})
    
    @classmethod
    def countdown_started(cls) -> "GameEvent":
        return cls(EventType.COUNTDOWN_STARTED)
    
    @classmethod
    def countdown_finished(cls) -> "GameEvent":
        return cls(EventType.COUNTDOWN_FINISHED)

    @classmethod
    def config_setup(cls) -> "GameEvent":
        return cls(EventType.CONFIG_SETUP, {"scales": ["C Major", "G Major"]})

