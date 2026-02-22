import io
import math
import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.io import wavfile


ENERGY_THRESHOLD = 0.001


def freq_to_note(freq: float) -> tuple[str, int]:
    notes = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']

    note_number = 12 * math.log2(freq / 440) + 49
    note_number = round(note_number)

    note = notes[(note_number - 1) % len(notes)]
    octave = (note_number + 8) // len(notes)

    return note, octave


def analyze_wav(filename: str) -> tuple[str, int, float]:
    # scipy.io.wavfile needs a file-like object
    fs, data = wavfile.read(filename)

    # If stereo, take one channel
    if len(data.shape) > 1:
        audio = data[:, 0]
    else:
        audio = data

    N = len(audio)

    # FFT
    X = rfft(audio)
    freqs = rfftfreq(N, 1 / fs)

    # Magnitude (scaled)
    x_mag = np.abs(X) / N

    mask = x_mag > ENERGY_THRESHOLD

    main_idx = int(np.argmax(x_mag))
    main_freq = float(freqs[main_idx])

    note, octave = freq_to_note(main_freq)

    return note, octave, main_freq
