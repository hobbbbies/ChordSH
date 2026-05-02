"""
Audio adapter using sounddevice for local microphone capture.
"""
import queue
import threading
from collections import deque
from typing import Callable
import numpy as np
from numpy.f2py.auxfuncs import throw_error
import sounddevice as sd
import soundfile as sf
from analyze import analyze_buffer
from core.events import GameEvent, EventType
from pathlib import Path
import traceback

WINDOW_SECONDS = 2.0
MIN_DETECTION_COUNT = 5
MIN_FREQUENCY = 70 


class SoundDeviceAudioAdapter:
    """
    Local audio capture using sounddevice.
    
    Implements the AudioAdapter protocol for microphone-based input.
    """
    
    def __init__(
        self,
        device: int | str | None = None,
        samplerate: int | None = None,
        channels: int = 1,
    ):
        self._device = device
        self._samplerate = samplerate
        self._channels = channels
        
        self._stream: sd.InputStream | None = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._streaming = False
        self._stream_thread: threading.Thread | None = None
        
        self._last_result: tuple[str, int, float] | None = None
        self._last_result_count = 0
        self._on_result: Callable[[str, int, float], None] | None = None
        
        # For stop signaling from UI
        self._stop_event = threading.Event()
        
        # Current target note from engine
        self._target_note: str | None = None
        self._target_interval: str | None = None

        # Raw recording buffer (for looper)
        self._record_stream: sd.InputStream | None = None
        self._record_buffer: list[np.ndarray] = []
        self._recording_raw = False

        # Playback (for looper) — multiple concurrent streams
        self._next_playback_id = 0
        self._playbacks: dict[int, tuple[threading.Thread, threading.Event]] = {}
        self._playbacks_lock = threading.Lock()
    
    # ---------- AudioAdapter Protocol ----------
    
    def start_stream(self, on_result: Callable[[str, int, float], None]) -> None:
        """Start streaming audio analysis."""
        if self._streaming:
            return
        
        self._on_result = on_result
        self._last_result = None
        self._stop_event.clear()
        self._drain_queue()
        
        # Resolve samplerate if not set
        if self._samplerate is None:
            device_info = sd.query_devices(self._device, 'input')
            self._samplerate = int(device_info['default_samplerate'])
        
        self._streaming = True
        self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._stream_thread.start()
    
    def stop_stream(self) -> tuple[str, int, float] | None:
        """Stop streaming and return last result."""
        if not self._streaming:
            return None
        
        self._stop_event.set()
        self._streaming = False
        
        if self._stream_thread:
            self._stream_thread.join(timeout=1.0)
            self._stream_thread = None
        
        return self._last_result
    
    def is_streaming(self) -> bool:
        """Check if currently streaming."""
        return self._streaming
    
    def on_event(self, event: GameEvent) -> None:
        """Handle game events from the engine."""
        if event.type == EventType.NEW_TARGET_NOTE:
            self._target_note = event.data.get("note")
            self._target_interval = event.data.get("interval")
            self.play_wav(filename=None)
    
    # ---------- Internal ----------
    
    def _audio_callback(self, indata, frames, time, status) -> None:
        """Called by sounddevice for each audio block."""
        if status:
            pass  # Could log status errors
        self._audio_queue.put(indata.copy())
    
    def _stream_loop(self) -> None:
        """Main streaming loop - runs in background thread."""
        window_samples = int(self._samplerate * WINDOW_SECONDS)
        rolling = deque(maxlen=window_samples)
        
        try:
            self._drain_queue()

            with sd.InputStream(
                samplerate=self._samplerate,
                device=self._device,
                channels=self._channels,
                callback=self._audio_callback
            ):
                while not self._stop_event.is_set():
                    try:
                        chunk = self._audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    
                    # Flatten to mono
                    mono = chunk[:, 0] if chunk.ndim > 1 else chunk.flatten()
                    rolling.extend(mono)
                    
                    # Only analyze with full window
                    if len(rolling) < window_samples:
                        continue
                    
                    audio = np.array(rolling, dtype=np.float32)
                    try:
                        note, freq, chord_name = analyze_buffer(audio, self._samplerate)
                        
                        # Should filter out background noise. may want to adjust this later
                        if freq < MIN_FREQUENCY:
                            continue

                        last_note = (note, freq)
                        if self._last_result != last_note:
                            self._last_result_count = 1
                        else:
                            self._last_result_count += 1
                        self._last_result = last_note

                        if self._on_result and self._last_result_count >= MIN_DETECTION_COUNT:
                            self._last_result_count = 0
                            self._last_result = None
                            if note is not None:
                                self._on_result(note, freq, chord_name)
                    except (ValueError, ZeroDivisionError):
                        pass  # Not enough signal, non catastrophic
        except Exception:
            traceback.print_exc()
        finally:
            self.stop_stream()
    
    def _drain_queue(self) -> None:
        """Clear any stale audio data."""
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

    # ---------- Raw Recording & Playback (Looper) ----------

    def record_buffer(self) -> None:
        """Start recording raw audio into an internal buffer."""
        if self._recording_raw:
            return

        if self._samplerate is None:
            device_info = sd.query_devices(self._device, 'input')
            self._samplerate = int(device_info['default_samplerate'])

        self._record_buffer = []
        self._recording_raw = True

        def callback(indata, frames, time, status):
            if self._recording_raw:
                self._record_buffer.append(indata.copy())

        self._record_stream = sd.InputStream(
            samplerate=self._samplerate,
            device=self._device,
            channels=self._channels,
            callback=callback,
        )
        self._record_stream.start()

    def stop_record_buffer(self) -> np.ndarray | None:
        """Stop recording and return captured audio."""
        self._recording_raw = False
        if self._record_stream:
            self._record_stream.stop()
            self._record_stream.close()
            self._record_stream = None

        if not self._record_buffer:
            return None

        buf = np.concatenate(self._record_buffer)
        self._record_buffer = []
        return buf

    def play_buffer(
        self,
        buffer: np.ndarray,
        loop: bool = False,
        on_loop: Callable[[], None] | None = None,
    ) -> int:
        """Play back audio, optionally looping. Returns a playback_id."""
        stop_event = threading.Event()

        with self._playbacks_lock:
            playback_id = self._next_playback_id
            self._next_playback_id += 1

        def _playback():
            try:
                # Each concurrent playback uses its own OutputStream
                out_stream = sd.OutputStream(
                    samplerate=self._samplerate,
                    channels=buffer.shape[1] if buffer.ndim > 1 else 1,
                    dtype=buffer.dtype,
                )
                out_stream.start()
                try:
                    while not stop_event.is_set():
                        if on_loop:
                            on_loop()
                        # Write buffer to this stream
                        out_stream.write(buffer)
                        if not loop:
                            break
                finally:
                    out_stream.stop()
                    out_stream.close()
            finally:
                with self._playbacks_lock:
                    self._playbacks.pop(playback_id, None)

        thread = threading.Thread(target=_playback, daemon=True)
        with self._playbacks_lock:
            self._playbacks[playback_id] = (thread, stop_event)
        thread.start()
        return playback_id

    def stop_playback(self, playback_id: int | None = None) -> None:
        """Stop a specific playback by ID, or all if None."""
        with self._playbacks_lock:
            if playback_id is not None:
                entry = self._playbacks.get(playback_id)
                if entry:
                    entries = [(playback_id, entry)]
                else:
                    entries = []
            else:
                entries = list(self._playbacks.items())

        for pid, (thread, stop_event) in entries:
            stop_event.set()
            thread.join(timeout=1.0)
            with self._playbacks_lock:
                self._playbacks.pop(pid, None)

    def is_playing(self) -> bool:
        """Check if any playback is currently active."""
        with self._playbacks_lock:
            return len(self._playbacks) > 0

    # ---------- WAV Playback ----------

    def play_wav(self, filename: str | None) -> None:
        """Plays WAV file to speakers"""
        try:
            root_wav = Path(__file__).parent.parent / "assets" / "root.wav"
            data, fs = sf.read(root_wav)
            sd.play(data, fs)
            sd.wait()
            if filename is not None:
                data, fs = sf.read(filename)
                sd.play(data, fs)
                sd.wait()
        except Exception:
            self.stop_stream()        
            raise FileNotFoundError
            
