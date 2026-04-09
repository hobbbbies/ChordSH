"""
Audio adapter using sounddevice for local microphone capture.
"""
import queue
import threading
from collections import deque
from typing import Callable
import numpy as np
import sounddevice as sd
from analyze import analyze_buffer


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
                        note, octave, freq = analyze_buffer(audio, self._samplerate)
                        
                        # Should filter out background noise. may want to adjust this later
                        if freq < MIN_FREQUENCY:
                            continue

                        last_note = (note, octave, freq)
                        if self._last_result != last_note:
                            self._last_result_count = 1
                        else:
                            self._last_result_count += 1
                        self._last_result = last_note

                        if self._on_result and self._last_result_count >= MIN_DETECTION_COUNT:
                            self._on_result(note, octave, freq)
                    except (ValueError, ZeroDivisionError):
                        pass  # Not enough signal
        except Exception:
            pass  # Could emit error event
        finally:
            self._streaming = False
    
    def _drain_queue(self) -> None:
        """Clear any stale audio data."""
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
