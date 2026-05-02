"""
Curses-based UI adapter implementation.
"""
import curses
from typing import Any
from core.events import GameEvent, EventType


class CursesUIAdapter:
    """
    Terminal UI using curses.
    
    Implements the UIAdapter protocol for terminal-based interaction.
    """
    
    def __init__(self, stdscr: "curses.window"):
        self._stdscr = stdscr
    
    # ---------- UIAdapter Protocol ----------
    
    def init(self) -> None:
        """Initialize curses screen."""
        curses.cbreak()
        curses.noecho()
        self._stdscr.keypad(True)
        self._stdscr.clear()
        self._stdscr.refresh()
        self._render_start_screen()
    
    def cleanup(self) -> None:
        """Restore terminal state."""
        curses.nocbreak()
        curses.echo()
        self._stdscr.keypad(False)
    
    def on_event(self, event: GameEvent) -> None:
        """Handle game events and render appropriately."""
        handlers = {
            EventType.MESSAGE: self._handle_message,
            EventType.DEBUG: self._handle_debug,
            EventType.ERROR: self._handle_error,
            EventType.NEW_TARGET_NOTE: self._handle_new_target,
            EventType.NOTE_DETECTED: self._handle_note_detected,
            EventType.NOTE_CORRECT: self._handle_note_correct,
            EventType.NOTE_INCORRECT: self._handle_note_incorrect,
            EventType.STREAMING_STARTED: self._handle_streaming_started,
            EventType.STREAMING_STOPPED: self._handle_streaming_stopped,
            EventType.GAME_STARTING: self._handle_game_starting,
            EventType.GAME_STARTED: self._handle_game_started,
            EventType.GAME_ENDED: self._handle_game_ended,
            EventType.COUNTDOWN_STARTED: self._handle_countdown_started,
            EventType.COUNTDOWN_FINISHED: self._handle_countdown_finished,
            EventType.CONFIG_SETUP: self._handle_config_setup,
            EventType.MASTER_MENU: self._handle_master_menu,
            EventType.LOOPER_RECORDING: self._handle_looper_recording,
            EventType.LOOPER_STOPPED: self._handle_looper_stopped,
            EventType.LOOPER_PLAYING: self._handle_looper_playing,
            EventType.LOOPER_STATUS: self._handle_looper_status,
        }
        handler = handlers.get(event.type)
        if handler:
            handler(event.data)
    
    def get_command(self) -> str | None:
        """Non-blocking input check."""
        self._stdscr.nodelay(True)
        try:
            key = self._stdscr.getch()
            if key == -1:
                return None
            return chr(key)
        except (curses.error, ValueError):
            return None
        finally:
            self._stdscr.nodelay(False)
    
    def wait_for_command(self) -> str:
        """Blocking wait for user input."""
        key = self._stdscr.getch()
        return chr(key)
    
    def wait_for_selection(self, items: list[str], use_enter_key = True) -> str:
        """Blocking wait for user to select from a list using arrow keys."""
        if not items:
            return "0"
        
        selected_idx = 0
        
        while True:
            # Highlight current selection
            for i, item in enumerate(items):
                row = i + 2
                self._stdscr.move(row, 0)
                self._stdscr.clrtoeol()
                
                if i == selected_idx:
                    # Highlighted item
                    self._stdscr.addstr(row, 2, f"> {i + 1}. {item}", curses.A_REVERSE)
                else:
                    # Normal item
                    self._stdscr.addstr(row, 2, f"  {i + 1}. {item}")
            
            self._stdscr.refresh()
            
            # Get key input
            key = self._stdscr.getch()
            
            if key == curses.KEY_UP:
                selected_idx = max(0, selected_idx - 1)
            elif key == curses.KEY_DOWN:
                selected_idx = min(len(items) - 1, selected_idx + 1)
            elif key in (curses.KEY_ENTER, 10, 13):  # Enter key
                if use_enter_key:
                    return str(selected_idx)
                else:
                    return '\n'
            elif key == ord('q'):
                return "q"
            elif key == ord('d') and not use_enter_key:
                return 'd'
    
    # ---------- Event Handlers ----------
    
    def _handle_message(self, data: dict[str, Any] | None) -> None:
        if data:
            self._message(data.get("text", ""), data.get("row", 0))
    
    def _handle_debug(self, data: dict[str, Any] | None) -> None:
        if data:
            self._debug(data.get("text", ""))
    
    def _handle_error(self, data: dict[str, Any] | None) -> None:
        if data:
            self._message(f"ERROR: {data.get('text', '')}", 3)
    
    def _handle_new_target(self, data: dict[str, Any] | None) -> None:
        if data:
            interval = data.get('interval', '')
            display = interval if interval else data.get('note', '?')
            self._message(f"Target note: {display}", 1)
    
    def _handle_note_detected(self, data: dict[str, Any] | None) -> None:
        if data:
            note = data.get("note", "?")
            freq = data.get("freq", 0.0)
            self._message(f"Live: {note}  {freq:.1f} Hz", 2)
            if data.get("chord_name"):
                self._message(f"Chord: {data.get('chord_name')}", 3)
    
    def _handle_note_correct(self, data: dict[str, Any] | None) -> None:
        self._debug("Success!")
    
    def _handle_note_incorrect(self, data: dict[str, Any] | None) -> None:
        if data:
            played = data.get("played", "?")
            expected = data.get("expected", "?")
            self._debug(f"Wrong! You played {played} instead of {expected}!")
    
    def _handle_streaming_started(self, data: dict[str, Any] | None) -> None:
        self._message("Streaming... press 'r' to stop", 0)
    
    def _handle_streaming_stopped(self, data: dict[str, Any] | None) -> None:
        pass
        # self._render_start_screen()
    
    def _handle_game_starting(self, data: dict[str, Any] | None) -> None:
        self._stdscr.clear()
    
    def _handle_game_started(self, data: dict[str, Any] | None) -> None:
        pass  # Already rendered in init()
    
    def _handle_game_ended(self, data: dict[str, Any] | None) -> None:
        score = data.get("score", 0) if data else 0
        self._stdscr.clear()
        self._message(f"Game Over! Final score: {score}", 0)

    def _handle_countdown_started(self, data: dict[str, Any] | None) -> None:
        self._stdscr.clear()
        self._message("Next note coming up...", 0)
    
    def _handle_countdown_finished(self, data: dict[str, Any] | None) -> None:
        # Clear the countdown message
        self._stdscr.move(0, 0)
        self._stdscr.clrtoeol()
        self._stdscr.refresh()

    def _handle_master_menu(self, data: dict[str, Any] | None) -> None:
        if data:
            items = data.get("games", [])
            self._stdscr.clear()
            self._message("=== ChordSH ===", 0)
            self._message("Select a game (↑/↓, Enter to select, q to quit):", 1)
            for i, game in enumerate(items):
                self._stdscr.addstr(i + 2, 2, f"  {i + 1}. {game}")
            self._stdscr.refresh()

    def _handle_looper_recording(self, data: dict[str, Any] | None) -> None:
        self._stdscr.clear()

    def _handle_looper_stopped(self, data: dict[str, Any] | None) -> None:
        self._stdscr.clear()

    def _handle_looper_playing(self, data: dict[str, Any] | None) -> None:
        self._stdscr.clear()

    def _handle_looper_status(self, data: dict[str, Any] | None) -> None:
        if not data:
            return
        
        state = data.get("state", "IDLE")
        duration = data.get("duration", 0.0)
        loop_count = data.get("loop_count", 0)
        
        # State labels
        state_labels = {
            "IDLE": "IDLE",
            "RECORDING": "[REC]",
            "PLAYING": "[PLAYING]",
            "PAUSED": "[PAUSED]",
        }
        label = state_labels.get(state, state)
        
        # Render header
        self._message(f"=== Looper ===  {label}", 0)
        
        # Render state-specific UI
        if state == "IDLE":
            self._message("Press ENTER to start recording", 1)
            self._message("Press 'q' to quit", 2)
        elif state == "RECORDING":
            self._message("Recording... press ENTER to stop", 1)
            self._stdscr.move(2, 0)
            self._stdscr.clrtoeol()
        elif state == "PAUSED":
            self._message(f"Recorded: {duration:.1f}s", 1)
            self._message("SPACE: play loop  |  ENTER: re-record  |  q: quit", 2)
        elif state == "PLAYING":
            self._message(f"Loop {loop_count}  ({duration:.1f}s)", 1)
            self._message("SPACE: stop  |  ENTER: re-record  |  q: quit", 2)

    def _handle_config_setup(self, data: dict[str, Any] | None) -> None:
        if data:
            scales = data.get("scales", [])
            self._stdscr.clear()
            self._message("Choose a scale (↑/↓ to navigate, Enter to select):", 0)
            for i, scale in enumerate(scales, 1):
                self._stdscr.addstr(i + 1, 2, f"{i}. {scale}")
            self._stdscr.refresh()
    
    
    # ---------- Rendering Helpers ----------
    
    def _message(self, msg: str, row: int) -> None:
        """Display message at specified row."""
        self._stdscr.move(row, 0)
        self._stdscr.clrtoeol()
        self._stdscr.addstr(row, 0, msg)
        self._stdscr.refresh()

    def _debug(self, msg: str) -> None:
        """Display debug message."""
        _, max_x = self._stdscr.getmaxyx()
        debug_row = 4
        self._stdscr.move(debug_row, 0)
        self._stdscr.clrtoeol()
        self._stdscr.addstr(debug_row, 0, f"DEBUG: {msg}"[:max_x - 1])
        self._stdscr.refresh()
    
    def _render_start_screen(self) -> None:
        """Render the initial game screen."""
        self._stdscr.clear()
        max_y, max_x = self._stdscr.getmaxyx()
        mid_y = max_y // 2
        self._stdscr.addstr(mid_y, 0, "Chord SH."[:max_x - 1])
        self._stdscr.addstr(mid_y + 1, 0, "Press 'r' to start recording."[:max_x - 1])
        self._stdscr.addstr(mid_y + 2, 0, "Press Q to quit."[:max_x - 1])
        self._stdscr.refresh()
