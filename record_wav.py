#!/usr/bin/env python3
"""
Simple script to record audio and save as WAV file in current directory.
Press Ctrl+C to stop recording.
"""
import argparse
import sys
import sounddevice as sd
import soundfile as sf
from datetime import datetime


def record_wav(duration=None, filename=None, samplerate=44100, channels=1, device=None):
    """
    Record audio and save to WAV file.
    
    Args:
        duration: Recording duration in seconds (None for manual stop with Ctrl+C)
        filename: Output filename (auto-generated if None)
        samplerate: Sample rate in Hz
        channels: Number of channels (1=mono, 2=stereo)
        device: Input device ID or name (None for default)
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.wav"
    
    print(f"Recording to: {filename}")
    print(f"Sample rate: {samplerate} Hz")
    print(f"Channels: {channels}")
    
    if duration:
        print(f"Duration: {duration} seconds")
        print("Recording...")
        recording = sd.rec(int(duration * samplerate), 
                          samplerate=samplerate, 
                          channels=channels,
                          device=device)
        sd.wait()
    else:
        print("Press Ctrl+C to stop recording...")
        import numpy as np
        
        # Use a list to collect chunks
        recorded_chunks = []
        
        def callback(indata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            recorded_chunks.append(indata.copy())
        
        try:
            with sd.InputStream(samplerate=samplerate, 
                               channels=channels,
                               device=device,
                               callback=callback):
                # Wait for KeyboardInterrupt
                while True:
                    sd.sleep(100)
        except KeyboardInterrupt:
            print("\nStopping recording...")
        
        # Concatenate all chunks
        if recorded_chunks:
            recording = np.concatenate(recorded_chunks, axis=0)
        else:
            print("No audio recorded")
            return None
    
    print(f"Saving to {filename}...")
    sf.write(filename, recording, samplerate)
    print(f"Done! Saved {len(recording)/samplerate:.2f} seconds of audio")
    return filename


def main():
    parser = argparse.ArgumentParser(description="Record audio to WAV file")
    parser.add_argument('-d', '--duration', type=float, 
                       help='Recording duration in seconds (omit for manual stop)')
    parser.add_argument('-o', '--output', type=str,
                       help='Output filename (default: recording_TIMESTAMP.wav)')
    parser.add_argument('-r', '--samplerate', type=int, default=44100,
                       help='Sample rate in Hz (default: 44100)')
    parser.add_argument('-c', '--channels', type=int, default=1,
                       help='Number of channels: 1=mono, 2=stereo (default: 1)')
    parser.add_argument('--device', type=str,
                       help='Input device ID or name')
    parser.add_argument('-l', '--list-devices', action='store_true',
                       help='List available audio devices and exit')
    
    args = parser.parse_args()
    
    if args.list_devices:
        print(sd.query_devices())
        return
    
    try:
        record_wav(
            duration=args.duration,
            filename=args.output,
            samplerate=args.samplerate,
            channels=args.channels,
            device=args.device
        )
    except KeyboardInterrupt:
        print("\nRecording cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
