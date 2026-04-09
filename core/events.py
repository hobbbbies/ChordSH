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
    def new_target(cls, note: str) -> "GameEvent":
        return cls(EventType.NEW_TARGET_NOTE, {"note": note})
    
    @classmethod
    def note_detected(cls, note: str, octave: int, freq: float) -> "GameEvent":
        return cls(EventType.NOTE_DETECTED, {"note": note, "octave": octave, "freq": freq})
    
    @classmethod
    def message(cls, text: str, row: int = 0) -> "GameEvent":
        return cls(EventType.MESSAGE, {"text": text, "row": row})
    
    @classmethod
    def error(cls, text: str) -> "GameEvent":
        return cls(EventType.ERROR, {"text": text})
