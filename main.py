import os 
import argparse
import queue
import sys
import tempfile
import atexit
import sounddevice as sd
import soundfile as sf
import curses
from ui.game_ui import GameUI
from analyze import analyze_wav, analyze_buffer
import subprocess
import time
import random
import numpy as np
from collections import deque
import threading

COMMANDS = {}
COMMANDS['E'] = 'ls'
C_MAJOR_SCALE = ["C", "D", "E", "F", "G", "A", "B"]
WINDOW_SECONDS = 2.0


# <--- Threading for reading input during recording ---> 
class KeyboardThread(threading.Thread):
    def __init__(self, stdscr, stop_key: str = 'r', name='keyboard-input-thread'):
        self.stdscr = stdscr
        self.stop_key = stop_key
        self.interrupt = threading.Event()
        super(KeyboardThread, self).__init__(name=name, daemon=True)
        self.start()

    def run(self):
        while not self.interrupt.is_set():
            try:
                key = self.stdscr.getch()
            except curses.error:
                continue

            if key == -1:
                time.sleep(0.02)
                continue

            try:
                if chr(key).lower() == self.stop_key:
                    self.interrupt.set()
            except ValueError:
                continue
                

    def getInterrupt(self):
        return self.interrupt.is_set()

    def stop(self):
        self.interrupt.set()
    

def parse_sh_note(note: str) -> str:
    if note in COMMANDS:
        command = COMMANDS[note]
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = (result.stdout or '').strip()
        error = (result.stderr or '').strip()

        if result.returncode == 0:
            return output if output else f"'{command}' executed successfully."
        return error if error else f"'{command}' failed with code {result.returncode}."

    return f"No command mapped for note {note}."

def parse_note(played: str, expected: str) -> bool:
    if played != expected:
        return False
        return f"Wrong! You played the {played} note instead of the {expected} note!"
    else:
        return True
        return "Success!"
    
def choose_note() -> str:
    return random.choice(C_MAJOR_SCALE)

def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument(
    '-l', '--list-devices', action='store_true',
    help='show list of audio devices and exit')
args, remaining = parser.parse_known_args()
if args.list_devices:
    print(sd.query_devices())
    parser.exit(0)
parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    parents=[parser])
parser.add_argument(
    'filename', nargs='?', metavar='FILENAME',
    help='audio file to store recording to')
parser.add_argument(
    '-d', '--device', type=int_or_str,
    help='input device (numeric ID or substring)')
parser.add_argument(
    '-r', '--samplerate', type=int, help='sampling rate')
parser.add_argument(
    '-c', '--channels', type=int, default=1, help='number of input channels')
parser.add_argument(
    '-t', '--subtype', type=str, help='sound file subtype (e.g. "PCM_24")')
args = parser.parse_args(remaining)

q = queue.Queue()


def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    q.put(indata.copy())


temp_files = []

def cleanup():
    """Remove all temporary recording files on exit."""
    for filename in temp_files:
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except OSError:
            pass

atexit.register(cleanup)

def _drain_audio_queue() -> None:
    while not q.empty():
        try:
            q.get_nowait()
        except queue.Empty:
            break


def record_input(stdscr, game_ui: GameUI) -> str | None:
    kthread = None
    try:
        _drain_audio_queue()

        if args.samplerate is None:
            device_info = sd.query_devices(args.device, 'input')
            # soundfile expects an int, sounddevice provides a float:
            args.samplerate = int(device_info['default_samplerate'])
        if args.filename is None:
            fd, args.filename = tempfile.mkstemp(prefix='input_',
                                            suffix='.wav', dir='')
            os.close(fd) # will be reopened by sd
            temp_files.append(args.filename)

        # Make sure the file is opened before recording anything:
        with sf.SoundFile(args.filename, mode='w+', samplerate=args.samplerate,
                        channels=args.channels, subtype=args.subtype) as file:
            with sd.InputStream(samplerate=args.samplerate, device=args.device,
                                channels=args.channels, callback=callback):
                filename = file.name
                stdscr.nodelay(True)
                game_ui.message("Recording... press 'r' again to stop", 0)
                kthread = KeyboardThread(stdscr)
                while True:
                    interrupt = kthread.getInterrupt()
                    if interrupt:
                        break
                    try:
                        file.write(q.get(timeout=0.1))
                    except queue.Empty:
                        continue

                kthread.stop()
                kthread.join(timeout=0.2)
                stdscr.nodelay(False)
                args.filename = None  # Reset for next recording
                return filename
    except KeyboardInterrupt:
        game_ui.message('Cancelling recording...', 0)
        return None
    except Exception as e:
        game_ui.message(f"Error: {type(e).__name__}: {str(e)}", 3)
        return None
    finally:
        if kthread is not None and kthread.is_alive():
            kthread.stop()
            kthread.join(timeout=0.2)
        stdscr.nodelay(False)

def record_stream(stdscr, game_ui: GameUI):
    """
    Stream audio continuously, analyzing a rolling window in real-time.
    Returns the last detected (note, octave, freq), or None on cancel.
    """
    kthread = None
    last_result = None
    try:
    
        if args.samplerate is None:
            device_info = sd.query_devices(args.device, 'input')
            args.samplerate = int(device_info['default_samplerate'])

        window_samples = int(args.samplerate * WINDOW_SECONDS)
        # Rolling buffer — old samples fall off the left automatically
        rolling = deque(maxlen=window_samples)
        game_ui.message("Streaming... press 'r' to stop", 0)
        stdscr.nodelay(True)
        kthread = KeyboardThread(stdscr)

        with sd.InputStream(samplerate=args.samplerate, device=args.device,
                            channels=args.channels, callback=callback):
            while not kthread.getInterrupt():
                try:
                    chunk = q.get(timeout=0.1)   # shape: (frames, channels)
                except queue.Empty:
                    continue

                # Flatten to mono and append to rolling window
                mono = chunk[:, 0] if chunk.ndim > 1 else chunk.flatten()
                rolling.extend(mono)

                # Only analyze once the buffer has a full window of audio
                if len(rolling) < window_samples:
                    continue

                audio = np.array(rolling, dtype=np.float32)
                try:
                    note, octave, freq = analyze_buffer(audio, args.samplerate)
                    last_result = (note, octave, freq)
                    game_ui.message(f"Live: {note}{octave}  {freq:.1f} Hz", 2)
                except (ValueError, ZeroDivisionError):
                    pass  # not enough signal yet

        kthread.stop()
        kthread.join(timeout=0.2)
        return last_result
    except KeyboardInterrupt:
        game_ui.message('Cancelling...', 0)
        return None
    except Exception as e:
        game_ui.message(f"Error: {type(e).__name__}: {str(e)}", 3)
        return None
    finally:
        if kthread is not None and kthread.is_alive():
            kthread.stop()
            kthread.join(timeout=0.2)
        stdscr.nodelay(False)

# def init_game_ui(stdscr) -> "GameUI":
#     game_ui = GameUI(stdscr)
#     return

def game_loop(game_ui, stdscr):
    current_note = choose_note()
    while True:
        cmd = stdscr.getkey().lower()
        if cmd == 'r':
            game_ui.message(f"Target note: {current_note}", 1)
            result = record_stream(stdscr, game_ui)
            if result:
                note, octave, freq = result
                note_text = f"Detected: {note}{octave} ({freq:.2f} Hz)"
                game_ui.message(note_text, 2)
                if not parse_note(note, current_note):
                    game_ui.debug(f"Wrong! You played {note} instead of {current_note}!")
                else:
                    game_ui.debug("Success!")
                    current_note = choose_note()
                    game_ui.message(f"Target note: {current_note}", 1)
            game_ui.render_start()
        elif cmd == 'q':
            break


def main(stdscr):
    game_ui = GameUI(stdscr)
    game_ui.init_screen()
    game_ui.render_start()
    game_loop(game_ui, stdscr)

if __name__ == "__main__":
    curses.wrapper(main)

