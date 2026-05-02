"""
Looper Game - record audio and loop it back like a looper pedal.

Press 'r' to start/stop recording, spacebar to toggle loop playback,
'q' to quit back to the master menu.
"""
import time
import numpy as np
from enum import Enum, auto
from typing import Callable
from .events import GameEvent, EventType
from .protocols import UIAdapter, AudioAdapter


class LooperState(Enum):
    """Current state of the looper."""
    IDLE = auto()
    RECORDING = auto()
    PLAYING = auto()
    PAUSED = auto()


class LooperGame:
    """
    Looper pedal game engine.

    Records audio from the user's instrument, then plays it back
    in a loop. The user can re-record or toggle playback.

    Designed to be run by a MasterEngine. Does NOT manage UI lifecycle.

    Controls:
        Enter/Return: Start/stop recording
        space: Toggle loop playback
        q: Quit back to master menu

    Usage:
        game = LooperGame(ui, audio)
        game.run()  # blocking loop, returns when player quits
    """

    NAME = "Looper"
    DESCRIPTION = "Record and loop audio like a looper pedal"

    def __init__(self, ui: UIAdapter, audio: AudioAdapter):
        self._ui = ui
        self._audio = audio
        self._running = False
        self._state = LooperState.IDLE
        self._buffer: np.ndarray | None = None
        self._loop_count = 0
        self._record_start_time: float = 0.0
        self._duration: float = 0.0
        self._event_listeners: list[Callable[[GameEvent], None]] = []
        self._loop_count_dirty = False

    # ---------- Public API ----------

    def run(self) -> None:
        """Blocking game loop. Returns when the player quits."""
        self._running = True
        self._emit(GameEvent.game_starting())
        self._show_status()
        try:
            while self._running:
                # Refresh loop counter from playback thread
                if self._state == LooperState.PLAYING and self._loop_count_dirty:
                    self._loop_count_dirty = False
                    self._show_status()

                cmd = self._ui.get_command()
                if cmd:
                    self._handle_command(cmd)
                else:
                    time.sleep(0.05)
        finally:
            self._cleanup()

    def add_event_listener(self, callback: Callable[[GameEvent], None]) -> None:
        """Register a callback to receive all game events."""
        self._event_listeners.append(callback)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def state(self) -> LooperState:
        return self._state

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def loop_count(self) -> int:
        return self._loop_count

    # ---------- Command Handling ----------

    def _handle_command(self, cmd: str) -> None:
        cmd = cmd.lower() if cmd != ' ' else cmd

        if cmd == 'q':
            self._running = False
        elif cmd in ('r', '\n'):
            self._toggle_recording()
        elif cmd == ' ':
            self._toggle_playback()

    def _toggle_recording(self) -> None:
        if self._state == LooperState.RECORDING:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        # Stop any ongoing playback first
        if self._state == LooperState.PLAYING:
            self._audio.stop_playback()

        self._state = LooperState.RECORDING
        self._buffer = None
        self._loop_count = 0
        self._record_start_time = time.time()
        self._audio.record_buffer()
        self._emit(GameEvent(EventType.LOOPER_RECORDING))
        self._show_status()

    def _stop_recording(self) -> None:
        buf = self._audio.stop_record_buffer()
        if buf is not None and len(buf) > 0:
            self._buffer = buf
            self._duration = time.time() - self._record_start_time
            self._state = LooperState.PAUSED
            self._emit(GameEvent(EventType.LOOPER_STOPPED))
        else:
            self._state = LooperState.IDLE
        self._show_status()

    def _toggle_playback(self) -> None:
        if self._state == LooperState.PLAYING:
            self._stop_playback()
        elif self._buffer is not None:
            self._start_playback()

    def _start_playback(self) -> None:
        if self._buffer is None:
            return
        self._state = LooperState.PLAYING
        self._loop_count = 0

        def on_loop():
            self._loop_count += 1
            self._loop_count_dirty = True

        self._audio.play_buffer(self._buffer, loop=True, on_loop=on_loop)
        self._emit(GameEvent(EventType.LOOPER_PLAYING))
        self._show_status()

    def _stop_playback(self) -> None:
        self._audio.stop_playback()
        self._state = LooperState.PAUSED
        self._emit(GameEvent(EventType.LOOPER_STOPPED))
        self._show_status()

    # ---------- Internal ----------

    def _emit(self, event: GameEvent) -> None:
        """Send event to UI and all listeners."""
        self._ui.on_event(event)
        for listener in self._event_listeners:
            listener(event)

    def _show_status(self) -> None:
        """Emit current looper state to UI."""
        self._emit(GameEvent(
            EventType.LOOPER_STATUS,
            {
                "state": self._state.name,
                "duration": self._duration,
                "loop_count": self._loop_count,
            }
        ))

    def _cleanup(self) -> None:
        """Stop all audio on exit."""
        if self._state == LooperState.RECORDING:
            self._audio.stop_record_buffer()
        if self._state == LooperState.PLAYING:
            self._audio.stop_playback()
        self._state = LooperState.IDLE
