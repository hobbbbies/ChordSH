"""
Interval Game - identify notes by their interval in a scale.

This is a specific game engine that can be run by the MasterEngine.
It does NOT manage UI lifecycle (init/cleanup) - that is the
MasterEngine's responsibility.
"""
import random
import time
from enum import Enum, auto
from typing import Callable
from .events import GameEvent, EventType
from .protocols import UIAdapter, AudioAdapter


class ScreenState(Enum):
    """Tracks which screen the user is currently viewing."""
    MENU = auto()
    GAME = auto()
    POST_ROUND = auto()


C_MAJOR_SCALE = ["C", "D", "E", "F", "G", "A", "B"]
G_MAJOR_SCALE = ["G", "A", "B", "C", "D", "E", "F#"]
scales = [C_MAJOR_SCALE, G_MAJOR_SCALE]
SCALE_NAMES = ["C Major", "G Major"]
# C_MAJOR_SCALE = ["B"]

ROMAN_NUMERALS = ["I", "II", "III", "IV", "V", "VI", "VII"]


class IntervalGame:
    """
    Interval recognition game engine.
    
    Presents random notes from a scale and challenges the player
    to identify them by playing the correct note on their instrument.
    
    Designed to be run by a MasterEngine. Does NOT manage UI lifecycle
    (init/cleanup) - that's the MasterEngine's responsibility.
    
    Usage:
        game = IntervalGame(ui, audio)
        game.run()  # blocking loop, returns when player quits
    """
    
    NAME = "Interval Game"
    DESCRIPTION = "Identify notes by their interval in a scale"
    
    def __init__(
        self,
        ui: UIAdapter,
        audio: AudioAdapter,
        scale: list[str] | None = None,
    ):
        self._ui = ui
        self._audio = audio
        self._scale = scale or C_MAJOR_SCALE
        self._scale_name = SCALE_NAMES[0] 
        
        self._running = False
        self._current_note: str | None = None
        self._score = 0
        self._round_resolved = False
        self._pending_next_round = False
        self._in_round = False
        self._screen_state = ScreenState.MENU
        
        # Optional event listeners for custom integrations
        self._event_listeners: list[Callable[[GameEvent], None]] = []
        
        # Future me: Check this out later
        # Register audio adapter to receive events if it has on_event method
        if hasattr(audio, 'on_event'):
            self.add_event_listener(audio.on_event)
    
    # ---------- Public API ----------
    
    def start(self) -> None:
        """Initialize game state."""
        self._running = True
    
    def stop(self) -> None:
        """End the game and clean up audio."""
        self._running = False
        self._audio.stop_stream()
        self._emit(GameEvent(EventType.GAME_ENDED, {"score": self._score}))
    
    def run(self) -> None:
        """
        Blocking game loop. Returns when the player quits back to the
        master menu.
        """
        self._emit(GameEvent.game_starting())
        self.start()
        self.menu_init()
        try:
            while self._running:
                # Handle screen state transitions
                if self._screen_state == ScreenState.POST_ROUND:
                    self._emit(GameEvent(EventType.GAME_ENDED, {"score": self._score}))
                    self._emit(GameEvent.message("Press 'r' to restart or 'q' to quit", row=1))
                    cmd = self._ui.wait_for_command()
                    self.handle_command(cmd)
                    continue
                
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
            self._audio.stop_stream()
    
    def config_setup(self) -> None:
        """
        Setup configuration for the game.
        Choose scale, choose speed, and auto vs manual mode.
        """
        self._emit(GameEvent.config_setup())
        scale_selection = self._ui.wait_for_selection(SCALE_NAMES)
        if scale_selection == "q":
            self._running = False
            return
        scale_index = int(scale_selection)
        self._scale = self._map_index_to_scale(scale_index)
        self._scale_name = self._get_scale_name(scale_index) 
    
    def start_game(self) -> None:
        """
        Start the game.
        """
        self._screen_state = ScreenState.MENU
        self._emit(GameEvent(EventType.GAME_STARTED))
        self._emit(GameEvent.message("Press 'r' to start recording, 'q' to quit"))
    
    def menu_init(self) -> None:
        if not self._running:
            return
        self.config_setup()
        if not self._running:
            return
        self.start_game()
    
    def handle_command(self, cmd: str) -> None:
        """
        Process a user command.
        
        Commands:
            'r': Toggle recording/streaming
            'q': Quit game (back to master menu)
        """
        cmd = cmd.lower()
        if cmd not in ('q', 'r'):
            return
        
        if self._screen_state == ScreenState.POST_ROUND:
            if cmd == 'r':
                self._score = 0
                self._screen_state = ScreenState.GAME
                self._start_recording()
            elif cmd == 'q':
                self._running = False
        
        elif self._screen_state == ScreenState.MENU:
            if cmd == 'q':
                self._running = False
            elif cmd == 'r':
                self._screen_state = ScreenState.GAME
                self._start_recording()
        
        elif self._screen_state == ScreenState.GAME:
            if cmd == 'q':
                if self._in_round:
                    self.end_round()
                else:
                    self._running = False
            elif cmd == 'r':
                if self._in_round:
                    self.end_round()
    
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
        """
        End the current round and transition to post-round screen.
        """
        self._in_round = False
        self._stop_recording()
        self._screen_state = ScreenState.POST_ROUND
    
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

        """TODO: Send interval to audioadapter"""

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
    
    def _on_note_detected(self, note: str, freq: float, chord_name: str | None) -> None:
        """Callback for real-time note detection during streaming."""
        self._emit(GameEvent.note_detected(note, freq, chord_name))
        self._check_note(note, chord_name)

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
        # Show scale info
        self._emit(GameEvent.message(f"Scale: {self._scale_name}", 0))
        self._new_target_note()

    def _check_note(self, played: str, chord_name: str | None) -> None:
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

    def _map_index_to_scale(self, index: int) -> list[str]:
        """Map index to scale."""
        return scales[index] if 0 <= index < len(scales) else scales[0]
    
    def _get_scale_name(self, index: int) -> str:
        """Get the name of the scale by index."""
        scale_names = ["C Major", "G Major"]
        return scale_names[index] if 0 <= index < len(scale_names) else "C Major"
