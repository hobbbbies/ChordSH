"""
Core game engine - pure logic, no UI dependencies.
"""
import random
import time
from typing import Callable
from .events import GameEvent, EventType
from .protocols import UIAdapter, AudioAdapter


C_MAJOR_SCALE = ["C", "D", "E", "F", "G", "A", "B"]


class GameEngine:
    """
    The game engine manages state and orchestrates the game loop.
    
    It communicates with the outside world through:
    - UIAdapter: for rendering and input
    - AudioAdapter: for audio capture and analysis
    - Event callbacks: for custom integrations
    
    Usage (curses):
        engine = GameEngine(ui_adapter, audio_adapter)
        engine.run()  # blocking loop
    
    Usage (web/async):
        engine = GameEngine(ui_adapter, audio_adapter)
        engine.start()
        # ... handle commands via engine.handle_command(cmd)
        engine.stop()
    """
    
    def __init__(
        self,
        ui: UIAdapter,
        audio: AudioAdapter,
        scale: list[str] | None = None,
    ):
        self._ui = ui
        self._audio = audio
        self._scale = scale or C_MAJOR_SCALE
        
        self._running = False
        self._current_note: str | None = None
        self._score = 0
        
        # Optional event listeners for custom integrations
        self._event_listeners: list[Callable[[GameEvent], None]] = []
    
    # ---------- Public API ----------
    
    def start(self) -> None:
        """Initialize game state and UI."""
        self._running = True
        self._ui.init()
        self._emit(GameEvent(EventType.GAME_STARTED))
        self._new_target_note()
        self._emit(GameEvent.message("Press 'r' to start recording, 'q' to quit"))
    
    def stop(self) -> None:
        """End the game and clean up."""
        self._running = False
        self._audio.stop_stream()
        self._emit(GameEvent(EventType.GAME_ENDED, {"score": self._score}))
        self._ui.cleanup()
    
    def run(self) -> None:
        """
        Blocking game loop for terminal-based UIs.
        For web/async, use start() + handle_command() + stop() instead.
        """
        self.start()
        try:
            while self._running:
                if self._audio.is_streaming():
                    # Non-blocking poll during streaming
                    cmd = self._ui.get_command()
                    if cmd:
                        self.handle_command(cmd)
                    else:
                        time.sleep(0.02)
                else:
                    # Blocking wait when idle
                    cmd = self._ui.wait_for_command()
                    self.handle_command(cmd)
        finally:
            self.stop()
    
    def handle_command(self, cmd: str) -> None:
        """
        Process a user command.
        
        Commands:
            'r': Toggle recording/streaming
            'q': Quit game
        """
        cmd = cmd.lower()
        
        if cmd == 'q':
            self._running = False
            
        elif cmd == 'r':
            if self._audio.is_streaming():
                self._stop_recording()
            else:
                self._start_recording()
    
    def add_event_listener(self, callback: Callable[[GameEvent], None]) -> None:
        """Register a callback to receive all game events."""
        self._event_listeners.append(callback)
    
    # ---------- Properties ----------
    
    @property
    def current_note(self) -> str | None:
        return self._current_note
    
    @property
    def score(self) -> int:
        return self._score
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    # ---------- Internal ----------
    
    def _emit(self, event: GameEvent) -> None:
        """Send event to UI and all listeners."""
        self._ui.on_event(event)
        for listener in self._event_listeners:
            listener(event)
    
    def _new_target_note(self) -> None:
        """Choose a new target note."""
        self._current_note = random.choice(self._scale)
        self._emit(GameEvent.new_target(self._current_note))
    
    def _start_recording(self) -> None:
        """Begin audio streaming."""
        self._emit(GameEvent(EventType.STREAMING_STARTED))
        self._emit(GameEvent.message(f"Target: {self._current_note}", row=1))
        self._audio.start_stream(self._on_note_detected)
    
    def _stop_recording(self) -> None:
        """Stop streaming and evaluate result."""
        self._audio.stop_stream()
        self._emit(GameEvent(EventType.STREAMING_STOPPED))
        
        # if result:
        #     note, octave, freq = result
        #     self._emit(GameEvent.note_detected(note, octave, freq))
        #     self._check_note(note)
    
    def _on_note_detected(self, note: str, octave: int, freq: float) -> None:
        """Callback for real-time note detection during streaming."""
        self._emit(GameEvent.note_detected(note, octave, freq))
        self._check_note(note)
    
    def _check_note(self, played: str) -> None:
        """Check if played note matches target."""
        if played == self._current_note:
            self._score += 1
            self._emit(GameEvent(EventType.NOTE_CORRECT, {"played": played, "expected": self._current_note}))
            self._new_target_note()
        else:
            self._emit(GameEvent(EventType.NOTE_INCORRECT, {"played": played, "expected": self._current_note}))
