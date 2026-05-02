"""Tests for core/looper_game.py — LooperGame engine."""
import numpy as np
import pytest
from core.looper_game import LooperGame, LooperState, LooperTrack
from core.events import EventType
from conftest import MockUIAdapter, MockAudioAdapter


FAKE_AUDIO = np.zeros(1000, dtype=np.float32)


class TestLooperGameInit:
    def test_creates_with_adapters(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = LooperGame(ui, audio)

        assert game._ui is ui
        assert game._audio is audio

    def test_initial_state(self):
        game = LooperGame(MockUIAdapter(), MockAudioAdapter())

        assert game.is_running is False
        assert game.state == LooperState.IDLE
        assert len(game.tracks) == 0


class TestLooperGameRecording:
    def test_start_recording(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()

        assert game.state == LooperState.RECORDING
        assert audio.record_buffer_count == 1
        assert any(e.type == EventType.LOOPER_RECORDING for e in ui.events)

    def test_stop_recording_appends_track(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()

        assert game.state == LooperState.PAUSED
        assert len(game.tracks) == 1
        assert any(e.type == EventType.LOOPER_STOPPED for e in ui.events)

    def test_recording_with_no_audio_goes_idle(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()

        assert game.state == LooperState.IDLE
        assert len(game.tracks) == 0

    def test_recording_stops_playback_first(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()
        game._play_track(0)
        game._start_recording()

        assert game.state == LooperState.RECORDING
        assert audio.stop_playback_count >= 1


class TestLooperGamePlayback:
    def test_play_track(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()
        game._play_track(0)

        assert game.state == LooperState.PLAYING
        assert game._playing_track_idx == 0
        assert audio.play_buffer_count == 1
        assert any(e.type == EventType.LOOPER_PLAYING for e in ui.events)

    def test_toggle_playback_stops_same_track(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()
        game._toggle_playback(0)
        game._toggle_playback(0)

        assert game.state == LooperState.PAUSED
        assert game._playing_track_idx is None
        assert audio.stop_playback_count >= 1

    def test_toggle_playback_switches_track(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()
        game._start_recording()
        game._stop_recording()
        game._toggle_playback(0)
        game._toggle_playback(1)

        assert game.state == LooperState.PLAYING
        assert game._playing_track_idx == 1
        assert audio.play_buffer_count == 2

    def test_toggle_on_empty_does_nothing(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = LooperGame(ui, audio)
        game._running = True

        game._toggle_playback(0)

        assert game.state == LooperState.IDLE

    def test_play_uses_loop_mode(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()
        game._play_track(0)

        assert audio._play_loop is True


class TestLooperGameTrackManagement:
    def test_delete_track(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()
        game._delete_track(0)

        assert len(game.tracks) == 0
        assert game.state == LooperState.IDLE

    def test_delete_playing_track_stops_playback(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()
        game._play_track(0)
        game._delete_track(0)

        assert game.state == LooperState.IDLE
        assert audio.stop_playback_count >= 1

    def test_delete_before_playing_adjusts_index(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()
        game._start_recording()
        game._stop_recording()
        game._play_track(1)
        game._delete_track(0)

        assert game._playing_track_idx == 0
        assert len(game.tracks) == 1

    def test_delete_out_of_range_does_nothing(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = LooperGame(ui, audio)
        game._running = True

        game._delete_track(5)

        assert len(game.tracks) == 0


class TestLooperGameMultipleTracks:
    def test_multiple_recordings_append(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()
        game._start_recording()
        game._stop_recording()

        assert len(game.tracks) == 2

    def test_format_track_list_empty(self):
        game = LooperGame(MockUIAdapter(), MockAudioAdapter())
        items = game._format_track_list()
        assert items == ["(no tracks yet)"]

    def test_format_track_list_with_tracks(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()

        items = game._format_track_list()
        assert len(items) == 1
        assert "Track 1:" in items[0]

    def test_format_shows_playing_indicator(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()
        game._play_track(0)

        items = game._format_track_list()
        assert "[playing]" in items[0]


class TestLooperGameRun:
    def test_run_emits_game_starting(self):
        ui = MockUIAdapter()
        ui.queue_commands('q')
        audio = MockAudioAdapter()

        game = LooperGame(ui, audio)
        game.run()

        starting_events = ui.get_events_of_type(EventType.GAME_STARTING)
        assert len(starting_events) == 1

    def test_run_quits_on_q(self):
        ui = MockUIAdapter()
        ui.queue_commands('q')
        audio = MockAudioAdapter()

        game = LooperGame(ui, audio)
        game.run()

        assert game.is_running is False
        assert game.state == LooperState.IDLE

    def test_run_record_and_quit(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        # Enter to record, Enter to stop, q to quit
        ui.queue_commands('\n', '\n', 'q')

        game = LooperGame(ui, audio)
        game.run()

        assert game.is_running is False
        assert len(game.tracks) == 1

    def test_run_delete_track(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        # Record, stop, delete track 0, quit
        ui.queue_commands('\n', '\n', 'd:0', 'q')

        game = LooperGame(ui, audio)
        game.run()

        assert len(game.tracks) == 0

    def test_run_play_and_quit(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        # Record, stop, play track 0, quit
        ui.queue_commands('\n', '\n', ' :0', 'q')

        game = LooperGame(ui, audio)
        game.run()

        assert audio.play_buffer_count == 1


class TestLooperGameCleanup:
    def test_cleanup_stops_recording(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._cleanup()

        assert game.state == LooperState.IDLE
        assert audio.stop_record_buffer_count >= 1

    def test_cleanup_stops_playback(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._start_recording()
        game._stop_recording()
        game._play_track(0)
        game._cleanup()

        assert game.state == LooperState.IDLE
        assert audio.stop_playback_count >= 1
