import io
import math
import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.io import wavfile
from scipy.signal import find_peaks as scipy_find_peaks
from mingus.core.chords import determine


ENERGY_THRESHOLD = 0.001
MIN_FREQ = 60
MAX_FREQ = 5000


def freq_to_note(freq: float) -> tuple[str, int]:
    notes = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']

    note_number = 12 * math.log2(freq / 440) + 49
    note_number = round(note_number)

    note = notes[(note_number - 1) % len(notes)]
    octave = (note_number + 8) // len(notes)

    return note, octave

# Sharp-to-flat mapping for mingus compatibility
SHARP_TO_FLAT = {
    'A#': 'Bb',
    'C#': 'Db',
    'D#': 'Eb',
    'F#': 'Gb',
    'G#': 'Ab',
}


def find_top_notes(x_mag, freqs, nums: int) -> list:
    """Find the top N frequencies by magnitude without modifying the array."""
    top_indices = np.argsort(x_mag)[-nums:][::-1]
    return [freqs[i] for i in top_indices]


def find_spectral_peaks(x_mag: np.ndarray, freqs: np.ndarray,
                        relative_threshold: float = 0.2) -> list[tuple[float, float]]:
    """Find all significant peaks in the spectrum.
    
    Returns list of (frequency, magnitude) tuples, sorted by magnitude descending.
    Only returns peaks above relative_threshold * max_magnitude.
    """
    # Find local maxima
    peak_indices, properties = scipy_find_peaks(x_mag, height=0)
    
    if len(peak_indices) == 0:
        return []
    
    peak_mags = x_mag[peak_indices]
    peak_freqs = freqs[peak_indices]
    
    # Filter by frequency range
    valid = (peak_freqs > MIN_FREQ) & (peak_freqs < MAX_FREQ)
    peak_mags = peak_mags[valid]
    peak_freqs = peak_freqs[valid]
    
    if len(peak_mags) == 0:
        return []
    
    # Filter by relative threshold
    threshold = relative_threshold * peak_mags.max()
    above = peak_mags >= threshold
    peak_mags = peak_mags[above]
    peak_freqs = peak_freqs[above]
    
    # Sort by magnitude descending
    order = np.argsort(peak_mags)[::-1]
    return [(float(peak_freqs[i]), float(peak_mags[i])) for i in order]


def filter_harmonics(peaks: list[tuple[float, float]],
                     tolerance: float = 0.03) -> list[tuple[float, float]]:
    """Remove peaks that are harmonics of stronger (earlier) peaks.
    
    A peak at freq F is considered a harmonic of a fundamental at freq F0
    if F / F0 is close to an integer (within tolerance).
    """
    fundamentals = []
    for freq, mag in peaks:
        is_harmonic = False
        for fund_freq, _ in fundamentals:
            ratio = freq / fund_freq
            if abs(ratio - round(ratio)) < tolerance and round(ratio) >= 2:
                is_harmonic = True
                break
        if not is_harmonic:
            fundamentals.append((freq, mag))
    return fundamentals


def peaks_to_pitch_classes(peaks: list[tuple[float, float]]) -> list[str]:
    """
    Convert peak frequencies to unique pitch class names (no octave).
    """
    seen = set()
    pitch_classes = []
    for freq, _ in peaks:
        note, _ = freq_to_note(freq)
        if note not in seen:
            seen.add(note)
            pitch_classes.append(note)
    return pitch_classes


def identify_chord(pitch_classes: list[str]) -> tuple(str, str) | tuple(None, None):
    """Identify chord name from pitch classes using mingus.
    
    Tries sharp spelling first, then flat spelling for mingus compatibility.
    """
    # len of 2 will just give interval 
    # COULD BE SOURCE OF ERROR DOWN THE ROAD
    if len(pitch_classes) == 2:
        pitch_classes = [pitch_classes[0]]
    
    # Try with original (sharp) spelling
    result = determine(pitch_classes, shorthand=True)
    if result:
        note = result[0][0]
        chord = result[0]
        return (note, chord)
    
    # Try with flat spelling
    flat_classes = [SHARP_TO_FLAT.get(n, n) for n in pitch_classes]
    result = determine(flat_classes, shorthand=True)
    if result:
        note = result[0][0]
        chord = result[0]
        return (note, chord)
    
    return (None, None)

def _compute_spectrum(audio: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """Compute windowed FFT magnitude spectrum and frequency bins."""
    N = len(audio)
    window = np.hanning(N)
    X = rfft(audio * window)
    freqs = rfftfreq(N, 1 / fs)
    x_mag = np.abs(X) / N
    return x_mag, freqs


def _prepare_audio(data: np.ndarray) -> np.ndarray:
    """Convert to mono if stereo."""
    if len(data.shape) > 1:
        return data[:, 0]
    return data


# Deprecated - use detect_chord instead
def analyze_wav(filename: str) -> tuple[str, float]:
    fs, data = wavfile.read(filename)

    if data.size == 0:
        raise ValueError("Recorded audio is empty")

    audio = _prepare_audio(data)
    x_mag, freqs = _compute_spectrum(audio, fs)

    # Apply energy threshold mask
    mask = (x_mag > ENERGY_THRESHOLD) & (freqs > MIN_FREQ) & (freqs < MAX_FREQ)
    if not np.any(mask):
        raise ValueError("No significant audio detected")
    x_mag_filtered = x_mag * mask

    top_note = find_top_notes(x_mag_filtered, freqs, 1)
    note, chord_name, pitch_classes = detect_chord(x_mag, freqs)

    note, _ = freq_to_note(top_note[0])
    return note, float(top_note[0]), chord_name

def _prepare_analyze_wav(filename: str) -> tuple[str, float]:
    fs, data = wavfile.read(filename)

    if data.size == 0:
        raise ValueError("Recorded audio is empty")

    audio = _prepare_audio(data)
    x_mag, freqs = _compute_spectrum(audio, fs)

    # Apply energy threshold mask
    mask = (x_mag > ENERGY_THRESHOLD) & (freqs > MIN_FREQ) & (freqs < MAX_FREQ)
    if not np.any(mask):
        raise ValueError("No significant audio detected")
    x_mag_filtered = x_mag * mask

    top_note = find_top_notes(x_mag_filtered, freqs, 1)
    return fs, audio, top_note, x_mag, freqs


def analyze_buffer(audio: np.ndarray, fs: int) -> tuple[str, float, str | None]:
    """Analyze a raw audio buffer instead of a WAV file."""
    if audio.size == 0:
        raise ValueError("Audio buffer is empty")

    audio = _prepare_audio(audio)
    x_mag, freqs = _compute_spectrum(audio, fs)

    # Apply energy threshold mask
    mask = (x_mag > ENERGY_THRESHOLD) & (freqs > MIN_FREQ) & (freqs < MAX_FREQ)
    if not np.any(mask):
        raise ValueError("No significant audio detected")
    x_mag_filtered = x_mag * mask

    top_note = find_top_notes(x_mag_filtered, freqs, 1)
    note, chord_name, pitch_classes = detect_chord(x_mag, freqs)

    return note, float(top_note[0]), chord_name


def detect_chord(x_mag: np.ndarray, freqs: np.ndarray) -> tuple[str | None, str | None, list[str]]:
    """Detect chord from audio buffer.
    
    Returns (chord_name, pitch_classes) where chord_name may be None
    if fewer than 2 distinct notes are found.
    """
    # if audio.size == 0:
    #     raise ValueError("Auedio buffer is empty")

    # FIX: Why do we call _prepare_audio on already prepared audio?
    # audio = _prepare_audio(audio)

    # And this gets called redundantly as well... 
    # x_mag, freqs = _compute_spectrum(audio, fs)

    # Find significant peaks
    peaks = find_spectral_peaks(x_mag, freqs)
    if not peaks:
        raise ValueError("No significant audio detected")

    # Remove harmonics to keep only fundamentals
    fundamentals = filter_harmonics(peaks)

    # Convert to pitch classes
    pitch_classes = peaks_to_pitch_classes(fundamentals)

    # Identify chord
    note, chord_name = identify_chord(pitch_classes)

    return note, chord_name, pitch_classes

    