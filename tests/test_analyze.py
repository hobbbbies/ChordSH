import numpy as np
import pytest
from scipy.io import wavfile
from pathlib import Path
from unittest.mock import patch

from analyze import analyze_wav, freq_to_note, identify_chord


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


class TestIdentifyChord:
    """Test chord identification with mocked mingus."""
    
    @patch('analyze.determine')
    def test_identifies_c_major_with_sharp_spelling(self, mock_determine):
        mock_determine.return_value = ['CM']
        
        root, chord = identify_chord(['C', 'E', 'G'])
        
        assert root == 'C'
        assert chord == 'CM'
        mock_determine.assert_called_once_with(['C', 'E', 'G'], shorthand=True)
    
    @patch('analyze.determine')
    def test_identifies_chord_with_flat_spelling_fallback(self, mock_determine):
        # First call (sharp spelling) returns empty, second call (flat spelling) succeeds
        mock_determine.side_effect = [[], ['BbM']]
        
        root, chord = identify_chord(['A#', 'D', 'F'])
        
        assert root == 'B'
        assert chord == 'BbM'
        assert mock_determine.call_count == 2
        # First call with sharp spelling
        assert mock_determine.call_args_list[0][0][0] == ['A#', 'D', 'F']
        # Second call with flat spelling
        assert mock_determine.call_args_list[1][0][0] == ['Bb', 'D', 'F']
    
    @patch('analyze.determine')
    def test_returns_none_for_single_note(self, mock_determine):
        root, chord = identify_chord(['C'])
        
        assert root is None
        assert chord is None
        mock_determine.assert_not_called()
    
    @patch('analyze.determine')
    def test_returns_none_for_two_notes(self, mock_determine):
        root, chord = identify_chord(['C', 'E'])
        
        assert root is None
        assert chord is None
        mock_determine.assert_not_called()
    
    @patch('analyze.determine')
    def test_returns_none_when_mingus_finds_no_match(self, mock_determine):
        mock_determine.return_value = []
        
        root, chord = identify_chord(['C', 'D', 'E'])
        
        assert root is None
        assert chord is None
        assert mock_determine.call_count == 2  # Tries both sharp and flat
    
    @patch('analyze.determine')
    def test_handles_first_inversion(self, mock_determine):
        mock_determine.return_value = ['CM']
        
        root, chord = identify_chord(['E', 'G', 'C'])
        
        assert root == 'C'
        assert chord == 'CM'
        mock_determine.assert_called_once_with(['E', 'G', 'C'], shorthand=True)