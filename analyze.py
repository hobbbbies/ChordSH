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

def find_top_notes(x_mag, freqs, nums: int) -> list:
    # Make a copy of freqs 
    # Pop largest index
    # Repeat until we have nums popped indices 
    popped_indices = []
    while len(popped_indices) < nums:
        greatest = int(np.argmax(x_mag))
        popped_indices.append(greatest)
        x_mag = np.delete(x_mag, greatest)
    
    top_notes = []
    for i in range(nums):
        top_notes.append(freqs[popped_indices[i]])
 
    return top_notes

def analyze_wav(filename: str) -> tuple[str, int, float]:
    # scipy.io.wavfile needs a file-like object
    fs, data = wavfile.read(filename)

    if data.size == 0:
        raise ValueError("Recorded audio is empty")

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

    # main_idx = int(np.argmax(x_mag))
    # main_freq = float(freqs[main_idx])

    top_note = find_top_notes(x_mag, freqs, 1)

    note, octave = freq_to_note(top_note[0])

    return note, octave, top_note[0]

def analyze_buffer(audio: np.ndarray, fs: int) -> tuple[str, int, float]:
    """Analyze a raw audio buffer instead of a WAV file."""
    if audio.size == 0:
        raise ValueError("Audio buffer is empty")

    # If stereo, take one channel
    if len(audio.shape) > 1:
        audio = audio[:, 0]

    N = len(audio)
    X = rfft(audio)
    freqs = rfftfreq(N, 1 / fs)
    x_mag = np.abs(X) / N

    top_note = find_top_notes(x_mag, freqs, 1)
    note, octave = freq_to_note(top_note[0])
    return note, octave, float(top_note[0])


# # Break down into sliding windows
# def analyze_whole_wav(filename: str) -> list[tuple[str, int, float]]:
#     fs, data = wavfile.read(filename)
    
#     # If stereo, take one channel
#     if len(data.shape) > 1:
#         audio = data[:, 0]
#     else:
#         audio = data

#     N = len(audio)
#     time = 
#     return