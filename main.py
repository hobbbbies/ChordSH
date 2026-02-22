import os 
import argparse
import queue
import sys
import tempfile
import atexit
import sounddevice as sd
import soundfile as sf
from analyze import analyze_wav

import threading

# <--- Threading for reading input during recording ---> 
class KeyboardThread(threading.Thread):
    def __init__(self, input_cbk = None, name='keyboard-input-thread'):
        self.input_cbk = input_cbk
        self.interrupt = False
        super(KeyboardThread, self).__init__(name=name, daemon=True)
        self.start()

    def run(self):
        while True:
            key = input()
            if self.input_cbk:
                self.input_cbk(key) # waits to get input + Return
            if key == 'r':
                self.interrupt = True
                

    def getInterrupt(self):
        return self.interrupt

def get_input_callback(key):
    print(key)
    

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


def record_input() -> str:
    try:
        if args.samplerate is None:
            device_info = sd.query_devices(args.device, 'input')
            # soundfile expects an int, sounddevice provides a float:
            args.samplerate = int(device_info['default_samplerate'])
        if args.filename is None:
            fd, args.filename = tempfile.mkstemp(prefix='input_',
                                            suffix='.wav', dir='')
            os.close(fd) # will be reopened by sd 

        # Make sure the file is opened before recording anything:
        with sf.SoundFile(args.filename, mode='w+', samplerate=args.samplerate,
                        channels=args.channels, subtype=args.subtype) as file:
            with sd.InputStream(samplerate=args.samplerate, device=args.device,
                                channels=args.channels, callback=callback):
                filename = file.name
                print('#' * 80)
                print("press 'r' to stop the recording")
                print('#' * 80)
                kthread = KeyboardThread(input_cbk=get_input_callback)
                while True:
                    interrupt = kthread.getInterrupt()
                    if interrupt:
                        break
                    file.write(q.get())
                return filename
    except KeyboardInterrupt:
        print('\nCancelling recording... ')
    except Exception as e:
        parser.exit(1, type(e).__name__ + ': ' + str(e))

filename = ""
while 1:
    cmd = input("Press 'r' to start recording.")
    if cmd == 'r':
        filename = record_input()
        note, octave, main_frequency = analyze_wav(filename)
        print(note, octave)
    
def cleanup():
    if len(filename) > 0:
        os.remove(filename)
    parser.exit(0)
    
atexit.register(cleanup)