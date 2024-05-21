from silero_vad import SileroVAD
import soundfile as sf
import numpy as np

# Name the output file
output_file = 'speech_only.wav'

# Initialize SileroVAD
onnx_model = 'silero_vad.onnx'

# Load an audio file (Audio should have single channel - Mono)
audio_file = "audiotest.wav"
audio_data, sample_rate = sf.read(audio_file)
print(len(audio_data))

# Ensure the audio is mono
if audio_data.ndim > 1:
    raise ValueError("Only mono audio is supported. Please convert your audio to mono.")
else:
    vad = SileroVAD(onnx_model=onnx_model)

    # Get speech timestamps
    speech_timestamps = vad.get_speech_timestamps(audio_file)

    speech_segments = []
    for segment in speech_timestamps:
        # print(segment)

        # Convert speech segments to seconds
        # Gives me speech timestamps excluding silence in seconds
        # print(segment['start']/44100, segment['end']/44100) 
        speech_segments.append(audio_data[segment['start']:segment['end']])

    speech_only=np.concatenate(speech_segments)

    sf.write(output_file,speech_only,sample_rate)
    print("Saved as", output_file)


        
