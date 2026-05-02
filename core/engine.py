"""
Backwards compatibility re-exports.

The original GameEngine has been refactored into IntervalGame.
Import from core.interval_game for the game logic, or use
core.master_engine.MasterEngine for the top-level menu engine.
"""
from .interval_game import (
    IntervalGame as GameEngine,
    IntervalGame,
    ScreenState,
    C_MAJOR_SCALE,
    G_MAJOR_SCALE,
    scales,
    ROMAN_NUMERALS,
)