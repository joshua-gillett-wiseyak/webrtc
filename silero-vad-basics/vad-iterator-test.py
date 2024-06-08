import pyaudio
import numpy as np
from silero_vad import VADIterator
import soundfile as sf

# Instantiate VADIterator with desired parameters
vad_iterator = VADIterator(threshold=0.3, window_size_ms=96)

# Define parameters for audio capture
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024  # Adjust as needed
RECORD_SECONDS = 10  # Duration to record in seconds

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open audio stream
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True)

print(f"Recording for {RECORD_SECONDS} seconds...")

# Initialize variables for recording
frames = []
speech_segments = []
recorded_frames = 0

# Keep capturing audio data in chunks and pass them to the VADIterator
try:
    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        # Read audio data in chunks
        audio_data = stream.read(CHUNK)
                
        # Append audio chunk to recorded frames
        frames.append(audio_data)
        
except KeyboardInterrupt:
    print("Recording stopped.")

# Close the audio stream and terminate PyAudio
stream.stop_stream()
stream.close()
p.terminate()

audio_data_bytes = b''.join(frames)

# Convert raw audio data to NumPy array
entire_frame = np.frombuffer(audio_data_bytes, dtype=np.int16)

# print(list(vad_iterator(entire_frame, use_energy=True)))
# Pass audio chunk to VADIterator for speech detection and noise suppression
for speech_segment, background_noise_suppressed_frame in vad_iterator(entire_frame, use_energy=False):
    
    if speech_segment is not None:
        print(speech_segment, background_noise_suppressed_frame)

    #     # Append speech segment to speech_segments list
    # speech_segments.append(background_noise_suppressed_frame)

# Concatenate speech segments into a single array
concatenated_speech = np.concatenate(speech_segments)

# Save concatenated speech segments as a single audio file
sf.write("noise-free-output.wav", concatenated_speech, RATE)
print("Speech segments saved as output.wav.")
