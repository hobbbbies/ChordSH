"""
ChordSH - Note recognition game.

This is the refactored entry point using the clean architecture.
The game engine is decoupled from UI and audio implementations.
"""
import argparse
import curses
import sounddevice as sd

from core import MasterEngine
from adapters import CursesUIAdapter, SoundDeviceAudioAdapter


def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        '-l', '--list-devices', action='store_true',
        help='show list of audio devices and exit')
    args, remaining = parser.parse_known_args()
    
    if args.list_devices:
        print(sd.query_devices())
        parser.exit(0)
    
    parser = argparse.ArgumentParser(
        description="ChordSH - Note recognition game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parser])
    parser.add_argument(
        '-d', '--device', type=int_or_str,
        help='input device (numeric ID or substring)')
    parser.add_argument(
        '-r', '--samplerate', type=int,
        help='sampling rate')
    parser.add_argument(
        '-c', '--channels', type=int, default=1,
        help='number of input channels')
    parser.add_argument(
        '-t', '--trigger-port', type=str, default=None,
        help='serial port for Arduino trigger (e.g. /dev/cu.usbmodem1101)')
    
    return parser.parse_args(remaining)


def main(stdscr):
    """Main entry point for curses-based game."""
    args = parse_args()
    
    # Create adapters
    ui = CursesUIAdapter(stdscr)
    audio = SoundDeviceAudioAdapter(
        device=args.device,
        samplerate=args.samplerate,
        channels=args.channels,
    )
    
    # Optional: Arduino trigger (injects Enter key via serial)
    trigger = None
    if args.trigger_port:
        from adapters.trigger import SerialTrigger
        trigger = SerialTrigger(ui, port=args.trigger_port)
        trigger.start()

    # Create and run master engine (handles menu + game selection)
    try:
        engine = MasterEngine(ui, audio)
        engine.run()
    finally:
        if trigger:
            trigger.stop()


if __name__ == "__main__":
    curses.wrapper(main)
