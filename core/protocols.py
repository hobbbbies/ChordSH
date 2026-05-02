"""
Abstract protocols that UI and Audio adapters must implement.
These define the contract between the game engine and external systems.
"""
from typing import Callable, Protocol
import numpy as np
from .events import GameEvent


class UIAdapter(Protocol):
    """
    Protocol for UI implementations (curses, web, etc.).
    
    The UI adapter receives events from the game engine and renders them.
    It also provides input back to the engine.
    """
    
    def on_event(self, event: GameEvent) -> None:
        """
        Handle a game event (render it, update state, etc.).
        This is the main entry point for all engine -> UI communication.
        """
        ...
    
    def get_command(self) -> str | None:
        """
        Non-blocking check for user input.
        Returns command string ('r', 'q', etc.) or None if no input.
        """
        ...
    
    def wait_for_command(self) -> str:
        """
        Blocking wait for user input.
        Returns command string when user provides input.
        """
        ...
    
    def wait_for_selection(self, items: list[str], use_enter_key: bool = True) -> str:
        """
        Blocking wait for user to select from a list.
        Args:
            items: List of items to select from
            use_enter_key: If True, Enter selects and returns index.
                          If False, Enter returns '\\n' and extra keys
                          like 'd' and ' ' are available.
        Returns the selected index as a string, or a command string.
        """
        ...
    
    def init(self) -> None:
        """Initialize the UI (setup screen, connections, etc.)."""
        ...
    
    def cleanup(self) -> None:
        """Clean up resources (restore terminal, close connections, etc.)."""
        ...


class AudioAdapter(Protocol):
    """
    Protocol for audio capture implementations.
    
    Abstracts audio recording so the engine doesn't care if audio
    comes from local microphone, WebRTC stream, or uploaded file.
    """
    
    def start_stream(self, on_result: Callable[[str, float, str | None], None]) -> None:
        """
        Start streaming audio analysis.
        
        Args:
            on_result: Callback invoked with (note, freq, chord_name) on each detection
        """
        ...
    
    def stop_stream(self) -> tuple[str, float, str | None] | None:
        """
        Stop streaming and return the last detected result.
        Returns (note, freq, chord_name) or None if nothing detected.
        """
        ...
    
    def is_streaming(self) -> bool:
        """Check if currently streaming."""
        ...

    def record_buffer(self) -> None:
        """Start recording raw audio into an internal buffer."""
        ...

    def stop_record_buffer(self) -> np.ndarray | None:
        """
        Stop recording and return the captured audio as a numpy array.
        Returns None if nothing was recorded.
        """
        ...

    def play_buffer(self, buffer: np.ndarray, loop: bool = False, on_loop: Callable[[], None] | None = None) -> int:
        """
        Play back a recorded audio buffer.
        If loop=True, replay continuously until stop_playback() is called.
        on_loop is called at the start of each loop iteration.
        Returns a playback_id handle that can be passed to stop_playback.
        """
        ...

    def stop_playback(self, playback_id: int | None = None) -> None:
        """Stop ongoing playback. If playback_id is None, stop all."""
        ...

    def is_playing(self) -> bool:
        """Check if any playback is currently active."""
        ...
