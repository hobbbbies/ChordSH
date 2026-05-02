"""Tests for core/looper_game.py — LooperGame engine."""
import numpy as np
import pytest
from core.looper_game import LooperGame, LooperState
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
        assert game.duration == 0.0
        assert game.loop_count == 0


class TestLooperGameRecording:
    def test_r_starts_recording(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = LooperGame(ui, audio)
        game._running = True

        game._handle_command('r')

        assert game.state == LooperState.RECORDING
        assert audio.record_buffer_count == 1
        assert any(e.type == EventType.LOOPER_RECORDING for e in ui.events)

    def test_r_stops_recording(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._handle_command('r')  # Start
        game._handle_command('r')  # Stop

        assert game.state == LooperState.PAUSED
        assert game._buffer is not None
        assert any(e.type == EventType.LOOPER_STOPPED for e in ui.events)

    def test_recording_with_no_audio_goes_idle(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        # No fake buffer set — stop_record_buffer returns None
        game = LooperGame(ui, audio)
        game._running = True

        game._handle_command('r')  # Start
        game._handle_command('r')  # Stop

        assert game.state == LooperState.IDLE


class TestLooperGamePlayback:
    def test_space_starts_playback(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._handle_command('r')  # Start recording
        game._handle_command('r')  # Stop recording
        game._handle_command(' ')  # Play

        assert game.state == LooperState.PLAYING
        assert audio.play_buffer_count == 1
        assert any(e.type == EventType.LOOPER_PLAYING for e in ui.events)

    def test_space_stops_playback(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._handle_command('r')  # Record
        game._handle_command('r')  # Stop
        game._handle_command(' ')  # Play
        game._handle_command(' ')  # Stop

        assert game.state == LooperState.PAUSED
        assert audio.stop_playback_count >= 1

    def test_space_without_buffer_does_nothing(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = LooperGame(ui, audio)
        game._running = True

        game._handle_command(' ')

        assert game.state == LooperState.IDLE

    def test_play_uses_loop_mode(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._handle_command('r')
        game._handle_command('r')
        game._handle_command(' ')

        assert audio._play_loop is True
        assert audio._play_on_loop is not None


class TestLooperGameQuit:
    def test_q_quits(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = LooperGame(ui, audio)
        game._running = True

        game._handle_command('q')

        assert game.is_running is False

    def test_re_record_stops_playback_first(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._handle_command('r')  # Record
        game._handle_command('r')  # Stop
        game._handle_command(' ')  # Play
        game._handle_command('r')  # Re-record (should stop playback)

        assert game.state == LooperState.RECORDING
        assert audio.stop_playback_count >= 1


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
        ui.queue_commands('r', 'r', 'q')

        game = LooperGame(ui, audio)
        game.run()

        assert game.is_running is False
        assert game._buffer is not None


class TestLooperGameStatusEvents:
    def test_status_events_emitted(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._handle_command('r')  # Record
        game._handle_command('r')  # Stop

        status_events = ui.get_events_of_type(EventType.LOOPER_STATUS)
        assert len(status_events) >= 2

    def test_idle_status_on_init(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = LooperGame(ui, audio)
        game._running = True
        game._show_status()

        status_events = ui.get_events_of_type(EventType.LOOPER_STATUS)
        assert len(status_events) >= 1
        assert status_events[-1].data["state"] == "IDLE"
        assert status_events[-1].data["duration"] == 0.0
        assert status_events[-1].data["loop_count"] == 0


class TestLooperGameCleanup:
    def test_cleanup_stops_recording(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._handle_command('r')  # Start recording
        game._cleanup()

        assert game.state == LooperState.IDLE
        assert audio.stop_record_buffer_count >= 1

    def test_cleanup_stops_playback(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        audio.set_fake_buffer(FAKE_AUDIO)
        game = LooperGame(ui, audio)
        game._running = True

        game._handle_command('r')  # Record
        game._handle_command('r')  # Stop
        game._handle_command(' ')  # Play
        game._cleanup()

        assert game.state == LooperState.IDLE
        assert audio.stop_playback_count >= 1
