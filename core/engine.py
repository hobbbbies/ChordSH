"""
Core game engine - pure logic, no UI dependencies.
"""
import random
import time
from typing import Callable
from .events import GameEvent, EventType
from .protocols import UIAdapter, AudioAdapter


C_MAJOR_SCALE = ["C", "D", "E", "F", "G", "A", "B"]
G_MAJOR_SCALE = ["G", "A", "B", "C", "D", "E", "F#"]
scales = [C_MAJOR_SCALE, G_MAJOR_SCALE]
# C_MAJOR_SCALE = ["B"]

ROMAN_NUMERALS = ["I", "II", "III", "IV", "V", "VI", "VII"]


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
        self._round_resolved = False
        self._pending_next_round = False
        self._in_round = False
        
        # Optional event listeners for custom integrations
        self._event_listeners: list[Callable[[GameEvent], None]] = []
    
    # ---------- Public API ----------
    
    def start(self) -> None:
        """Initialize game state and UI."""
        self._running = True
        self._ui.init()
        self._emit(GameEvent(EventType.GAME_STARTED))
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
        self.config_setup()
        try:
            while self._running:
                # Handle pending round transition
                if self._pending_next_round:
                    self._pending_next_round = False
                    self._stop_recording()
                    self._interruptible_sleep(1.0)
                    if self._running and self._in_round:  # Only restart if not interrupted or ended
                        self._start_recording()
                
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
    
    def config_setup(self) -> None:
        """
        Setup configuration for the game.
        Choose scale, choose speed, and auto vs manual mode.
        """
        self._emit(GameEvent(EventType.CONFIG_SETUP, {"scales": ["C Major", "G Major"]}))
        scale_selection = self._ui.wait_for_selection()
        self._scale = self._map_index_to_scale(int(scale_selection)) 
    
    def handle_command(self, cmd: str) -> None:
        """
        Process a user command.
        
        Commands:
            'r': Toggle recording/streaming
            'q': Quit game
        """
        cmd = cmd.lower()
        
        if cmd == 'q':
            if self._in_round:
                self.end_round()
            else:
                self.stop()
            
        elif cmd == 'r':
            if self._in_round:
                self.end_round()
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
    
    def end_round(self) -> None:
        """End the current round and show score."""
        self._in_round = False
        self._stop_recording()
        self._emit(GameEvent(EventType.GAME_ENDED, {"score": self._score}))
        self._emit(GameEvent.message("Press 'r' to restart or 'q' to quit", row=1))
    
    def _interruptible_sleep(self, duration: float) -> None:
        """Sleep while still checking for user input to allow early exit."""
        end_time = time.time() + duration
        while time.time() < end_time and self._running:
            cmd = self._ui.get_command()
            if cmd == 'r' or cmd == 'q':
                self.handle_command('q')
                if not self._running or not self._in_round:  # User quit or round ended
                    return
            time.sleep(0.05)  # Small sleep to avoid busy-waiting
    
    def _note_to_interval(self, note: str) -> str:
        """Convert a note to its Roman numeral interval in the current scale."""
        try:
            index = self._scale.index(note)
            return ROMAN_NUMERALS[index]
        except (ValueError, IndexError):
            return note

    def _new_target_note(self) -> None:
        """Choose a new target note."""
        self._current_note = random.choice(self._scale)
        interval = self._note_to_interval(self._current_note)
        self._emit(GameEvent.new_target(self._current_note, interval))
    
    def _start_recording(self) -> None:
        """Begin audio streaming."""
        self._emit(GameEvent(EventType.STREAMING_STARTED))
        self.start_round()
        self._audio.start_stream(self._on_note_detected)
    
    def _stop_recording(self, end_game: bool = False) -> None:
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

    def _start_countdown(self) -> bool:
        """Start a countdown before recording."""
        self._emit(GameEvent(EventType.COUNTDOWN_STARTED))
        self._interruptible_sleep(1.5)
        if self._running and self._in_round:  # Only emit if not interrupted or ended
            self._emit(GameEvent(EventType.COUNTDOWN_FINISHED))
            return True
        return False

    def start_round(self) -> None:
        """Start a new round."""
        self._round_resolved = False
        self._in_round = True
        if not self._start_countdown():
            return
        self._new_target_note()

    def _check_note(self, played: str) -> None:
        """Check if played note matches target."""
        if self._round_resolved or not self._in_round:
            return
        
        interval = self._note_to_interval(self._current_note)

        if played == self._current_note:
            self._round_resolved = True
            self._score += 1
            self._emit(GameEvent(EventType.NOTE_CORRECT, {"played": played, "expected": interval}))
            # Schedule next round transition in main loop (can't stop thread from within itself)
            self._pending_next_round = True
        else:
            self._emit(GameEvent(EventType.NOTE_INCORRECT, {"played": played, "expected": interval}))

    def _map_index_to_scale(self, index: int) -> str:
        """Map index to scale name."""
        return scales[index] if 0 <= index < len(scales) else scales[0]