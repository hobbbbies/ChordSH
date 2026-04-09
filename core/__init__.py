# Core game engine and protocols
from .engine import GameEngine
from .protocols import UIAdapter, AudioAdapter
from .events import GameEvent, EventType

__all__ = ["GameEngine", "UIAdapter", "AudioAdapter", "GameEvent", "EventType"]

# Expose C_MAJOR_SCALE for custom scale configuration
from .engine import C_MAJOR_SCALE
__all__.append("C_MAJOR_SCALE")
