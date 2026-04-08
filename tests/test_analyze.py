import numpy as np
import pytest
from scipy.io import wavfile
from pathlib import Path

from analyze import analyze_wav, freq_to_note


def test_freq_to_note_maps_a440_to_a4():
    note, octave = freq_to_note(440.0)

    assert note == "A"
    assert octave == 4


def test_analyze_wav_detects_440hz_tone(tmp_path):
    sample_rate = 44100
    duration_seconds = 1.0
    frequency = 440.0

    time_axis = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * frequency * time_axis) * np.iinfo(np.int16).max).astype(np.int16)

    wav_path = tmp_path / "tone.wav"
    wavfile.write(wav_path, sample_rate, audio)

    note, octave, detected_frequency = analyze_wav(str(wav_path))

    assert note == "A"
    assert octave == 4
    assert detected_frequency == pytest.approx(440.0, rel=0.05)


def test_analyze_wav_rejects_empty_audio(tmp_path):
    wav_path = tmp_path / "empty.wav"
    wavfile.write(wav_path, 44100, np.array([], dtype=np.int16))

    with pytest.raises(ValueError, match="Recorded audio is empty"):
        analyze_wav(str(wav_path))

def test_analyze_wav_asset_detects_c_note():
    wav_path = Path(__file__).parent / "assets" / "input_pu2oefzt.wav"

    note, octave, detected_frequency = analyze_wav(str(wav_path))

    assert note == "F#"
    assert octave == 2
    assert detected_frequency == 93.25132978723404