# Core game engine and protocols
from .engine import GameEngine  # backwards compat alias for IntervalGame
from .interval_game import IntervalGame
from .looper_game import LooperGame
from .master_engine import MasterEngine
from .protocols import UIAdapter, AudioAdapter
from .events import GameEvent, EventType

__all__ = [
    "GameEngine", "IntervalGame", "MasterEngine",
    "UIAdapter", "AudioAdapter", "GameEvent", "EventType",
]

# Expose C_MAJOR_SCALE for custom scale configuration
from .interval_game import C_MAJOR_SCALE
__all__.append("C_MAJOR_SCALE")
