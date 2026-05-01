import numpy as np
import pytest
from scipy.io import wavfile
from pathlib import Path
from unittest.mock import patch

from analyze import analyze_wav, freq_to_note, identify_chord, find_spectral_peaks, _prepare_analyze_wav, filter_harmonics


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

    note, detected_frequency, _ = analyze_wav(str(wav_path))

    assert note == "A"
    assert detected_frequency == pytest.approx(440.0, rel=0.05)


def test_analyze_wav_rejects_empty_audio(tmp_path):
    wav_path = tmp_path / "empty.wav"
    wavfile.write(wav_path, 44100, np.array([], dtype=np.int16))

    with pytest.raises(ValueError, match="Recorded audio is empty"):
        analyze_wav(str(wav_path))

def test_analyze_wav_asset_detects_c_note():
    wav_path = Path(__file__).parent / "assets" / "input_pu2oefzt.wav"

    note, detected_frequency, _ = analyze_wav(str(wav_path))

    assert note == "F#"
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
    def test_returns_note_only_for_single_note(self, mock_determine):
        mock_determine.side_effect = [['C'], ['C']]
        root, chord = identify_chord(['C'])
        
        assert root == 'C'
        assert chord == 'C'
    
    @patch('analyze.determine')
    def test_returns_single_note_for_two_notes(self, mock_determine):
        mock_determine.side_effect = [['C'], ['C', 'E']]
        root, chord = identify_chord(['C', 'E'])
        
        assert root == 'C'
        assert chord == 'C'
    
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


class TestFindSpectralPeaks:
    """Test spectral peak detection."""
    
    def test_finds_single_pure_tone(self):
        """Single sine wave should produce one dominant peak."""
        fs = 44100
        duration = 1.0
        freq = 440.0  # A4
        
        t = np.linspace(0, duration, int(fs * duration), endpoint=False)
        audio = np.sin(2 * np.pi * freq * t).astype(np.float32)
        
        from analyze import _compute_spectrum
        x_mag, freqs = _compute_spectrum(audio, fs)
        
        peaks = find_spectral_peaks(x_mag, freqs, relative_threshold=0.1)
        
        # Should find the 440Hz peak
        assert len(peaks) >= 1
        peak_freq, peak_mag = peaks[0]
        assert peak_freq == pytest.approx(440.0, abs=5.0)  # Within 5Hz
    
    def test_filters_low_magnitude_peaks(self):
        """Peaks below relative_threshold should be filtered out."""
        fs = 44100
        t = np.linspace(0, 1.0, fs, endpoint=False)
        
        # Strong 440Hz + weak 880Hz
        audio = (1.0 * np.sin(2 * np.pi * 440 * t) + 
                 0.05 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
        
        from analyze import _compute_spectrum
        x_mag, freqs = _compute_spectrum(audio, fs)
        
        # With high threshold, only strong peak survives
        peaks = find_spectral_peaks(x_mag, freqs, relative_threshold=0.3)
        assert len(peaks) == 1
        
        # With low threshold, both survive
        peaks = find_spectral_peaks(x_mag, freqs, relative_threshold=0.01)
        assert len(peaks) >= 2
    
    def test_filters_out_of_range_frequencies(self):
        """Peaks outside MIN_FREQ to MAX_FREQ should be filtered."""
        from analyze import MIN_FREQ, MAX_FREQ
        
        # Create synthetic spectrum with peaks at various frequencies
        freqs = np.linspace(0, 10000, 5000)
        x_mag = np.zeros(5000)
        
        # Calculate indices for specific frequencies
        # freq = index * (max_freq / num_bins)
        # index = freq * num_bins / max_freq
        low_idx = int(50 * 5000 / 10000)    # 50 Hz (below MIN_FREQ=60)
        mid_idx = int(1000 * 5000 / 10000)  # 1000 Hz (valid)
        high_idx = int(9000 * 5000 / 10000) # 9000 Hz (above MAX_FREQ=5000)
        
        x_mag[low_idx] = 1.0
        x_mag[mid_idx] = 1.0
        x_mag[high_idx] = 1.0
        
        peaks = find_spectral_peaks(x_mag, freqs, relative_threshold=0.5)
        
        # Only the middle peak should survive
        assert len(peaks) == 1
        peak_freq = peaks[0][0]
        assert MIN_FREQ < peak_freq < MAX_FREQ
        assert peak_freq == pytest.approx(1000.0, abs=50.0)
    
    def test_returns_peaks_sorted_by_magnitude(self):
        """Peaks should be sorted by magnitude descending."""
        fs = 44100
        t = np.linspace(0, 1.0, fs, endpoint=False)
        
        # Three tones with different amplitudes
        audio = (0.3 * np.sin(2 * np.pi * 200 * t) +
                 0.8 * np.sin(2 * np.pi * 400 * t) +
                 0.5 * np.sin(2 * np.pi * 600 * t)).astype(np.float32)
        
        from analyze import _compute_spectrum
        x_mag, freqs = _compute_spectrum(audio, fs)
        
        peaks = find_spectral_peaks(x_mag, freqs, relative_threshold=0.1)
        
        # Magnitudes should be descending
        mags = [mag for _, mag in peaks]
        assert mags == sorted(mags, reverse=True)
        
        # Strongest should be 400Hz
        assert peaks[0][0] == pytest.approx(400.0, abs=10.0)
    
    def test_returns_empty_for_silence(self):
        """Silent audio should return no peaks."""
        fs = 44100
        audio = np.zeros(fs, dtype=np.float32)
        
        from analyze import _compute_spectrum
        x_mag, freqs = _compute_spectrum(audio, fs)
        
        peaks = find_spectral_peaks(x_mag, freqs)
        assert len(peaks) == 0
    
    def test_real_audio_file(self):
        """Test with actual recorded audio."""
        wav_path = Path(__file__).parent / "assets" / "input_pu2oefzt.wav"
        fs, audio, top_note, x_mag, freqs = _prepare_analyze_wav(str(wav_path))
        
        peaks = find_spectral_peaks(x_mag, freqs)
        
        # Should find at least one peak in real audio
        assert len(peaks) > 0
        
        # All peaks should be tuples of (freq, mag)
        for peak in peaks:
            assert len(peak) == 2
            freq, mag = peak
            assert isinstance(freq, float)
            assert isinstance(mag, float)
            assert mag > 0


class TestFilterHarmonics:
    """Test harmonic filtering to remove overtones."""
    
    def test_filters_perfect_harmonic(self):
        """2nd harmonic (2x frequency) should be filtered out."""
        # Fundamental at 200Hz, 2nd harmonic at 400Hz (exact 2:1 ratio)
        peaks = [(200.0, 1.0), (400.0, 0.5)]
        
        result = filter_harmonics(peaks)
        
        # Only fundamental should remain
        assert len(result) == 1
        assert result[0] == (200.0, 1.0)
    
    def test_filters_third_harmonic(self):
        """3rd harmonic (3x frequency) should be filtered out."""
        # Fundamental at 150Hz, 3rd harmonic at 450Hz (exact 3:1 ratio)
        peaks = [(150.0, 1.0), (450.0, 0.3)]
        
        result = filter_harmonics(peaks)
        
        assert len(result) == 1
        assert result[0] == (150.0, 1.0)
    
    def test_filters_multiple_harmonics(self):
        """All harmonics of a fundamental should be filtered."""
        # Fundamental at 100Hz with 2nd, 3rd, 4th harmonics
        peaks = [
            (100.0, 1.0),   # Fundamental
            (200.0, 0.5),   # 2nd harmonic
            (300.0, 0.3),   # 3rd harmonic
            (400.0, 0.2),   # 4th harmonic
        ]
        
        result = filter_harmonics(peaks)
        
        assert len(result) == 1
        assert result[0] == (100.0, 1.0)
    
    def test_keeps_non_harmonic_peaks(self):
        """Two unrelated frequencies should both be kept."""
        # 200Hz and 350Hz are not harmonically related
        peaks = [(200.0, 1.0), (350.0, 0.8)]
        
        result = filter_harmonics(peaks)
        
        # Both should remain
        assert len(result) == 2
        assert result[0] == (200.0, 1.0)
        assert result[1] == (350.0, 0.8)
    
    def test_keeps_peaks_just_outside_tolerance(self):
        """Peaks outside tolerance threshold should not be filtered."""
        # Default tolerance is 0.03
        # 200Hz and 408Hz: ratio = 408/200 = 2.04
        # Distance from nearest integer (2): 0.04
        # This is > 0.03 tolerance, so should NOT be filtered
        peaks = [(200.0, 1.0), (408.0, 0.5)]  # ratio = 2.04, just outside
        
        result = filter_harmonics(peaks, tolerance=0.03)
        
        # Both should remain
        assert len(result) == 2
    
    def test_filters_peaks_just_inside_tolerance(self):
        """Peaks within tolerance should be filtered."""
        # 200Hz and 404Hz: ratio = 404/200 = 2.02
        # Distance from nearest integer (2): 0.02
        # This is < 0.03 tolerance, so SHOULD be filtered
        peaks = [(200.0, 1.0), (404.0, 0.5)]
        
        result = filter_harmonics(peaks, tolerance=0.03)
        
        # Only fundamental should remain
        assert len(result) == 1
        assert result[0] == (200.0, 1.0)
    
    def test_preserves_order_of_fundamentals(self):
        """Non-harmonic peaks should maintain their input order."""
        # Three unrelated frequencies
        peaks = [(100.0, 0.5), (250.0, 1.0), (450.0, 0.3)]
        
        result = filter_harmonics(peaks)
        
        # All should remain in original order
        assert len(result) == 3
        assert result[0] == (100.0, 0.5)
        assert result[1] == (250.0, 1.0)
        assert result[2] == (450.0, 0.3)
    
    def test_weaker_fundamental_with_stronger_harmonic(self):
        """If fundamental comes first, its harmonic is filtered regardless of magnitude."""
        # Fundamental at 200Hz (weak), 2nd harmonic at 400Hz (strong)
        peaks = [(200.0, 0.3), (400.0, 1.0)]
        
        result = filter_harmonics(peaks)
        
        # Fundamental is kept because it comes first, harmonic filtered
        assert len(result) == 1
        assert result[0] == (200.0, 0.3)
    
    def test_ignores_subharmonics(self):
        """Lower frequencies are not filtered as 'harmonics' of higher ones."""
        # 400Hz and 200Hz: ratio = 200/400 = 0.5 (subharmonic, not harmonic)
        # round(0.5) = 0, which is < 2, so should NOT be filtered
        peaks = [(400.0, 1.0), (200.0, 0.8)]
        
        result = filter_harmonics(peaks)
        
        # Both should remain (200Hz is not a harmonic of 400Hz)
        assert len(result) == 2
    
    def test_empty_list(self):
        """Empty input should return empty output."""
        result = filter_harmonics([])
        assert result == []
    
    def test_single_peak(self):
        """Single peak has no harmonics to filter."""
        peaks = [(440.0, 1.0)]
        
        result = filter_harmonics(peaks)
        
        assert len(result) == 1
        assert result[0] == (440.0, 1.0)
    
    def test_chord_notes_not_filtered(self):
        """Notes in a chord (D-F-A) should not be filtered as harmonics."""
        # D3=146.83, F3=174.61, A3=220.0
        # These ratios are not close to integers
        peaks = [(146.83, 0.5), (174.61, 0.8), (220.0, 0.6)]
        
        result = filter_harmonics(peaks)
        
        # All three should remain (chord notes, not harmonics)
        assert len(result) == 3
