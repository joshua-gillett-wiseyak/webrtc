import requests
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
import asyncio
import numpy as np
import tempfile
from silero_vad import SileroVAD
import soundfile as sf

onnx_model = './silero-vad-basics/silero_vad.onnx'
vad = SileroVAD(onnx_model=onnx_model)

SIGNALING_SERVER_URL = 'http://localhost:9999' 
ID = "answerer01" 
RATE=44100 # Hardcode RATE for now

received_chunks=[]
async_lock = asyncio.Lock()

buffer=[] # buffer to store combined 20 audio-chunks as one chunk
i=0 # buffer index
hasSpeech={} # dictionary to store if buffer's index has speech; added after appling VAD to the merged chunks

# Coroutine to merge 20 chunks as single chunk from received_chunks and check if the combined chunk has speech or not
async def process_messages():

    temp_buffer=[] # To hold 20 chunks from received_chunks before they are combined and placed in buffer
    global i # to increment index of buffer which contains combined 20 chunks as 1 chunk

    while True:
        async with async_lock:
            while received_chunks:
                if len(temp_buffer) < 20:
                    temp_buffer.append(received_chunks.pop(0))

                if len(temp_buffer) == 20:
                    combination_of_20_chunks = b''.join(temp_buffer)
                    buffer.append(combination_of_20_chunks)
                    # print(buffer)
                    temp_buffer.clear()

                    audio_array = np.frombuffer(combination_of_20_chunks, dtype=np.int16)

                    # Create tmppath as vad expects wav path 
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmpfile:
                        sf.write(tmpfile.name, audio_array, RATE)
                        tmpfile_path = tmpfile.name

                    speech_timestamps = vad.get_speech_timestamps(tmpfile_path)
                    hasSpeech[i] = any(speech_timestamps)
                    i += 1

                print(hasSpeech)
        await asyncio.sleep(0.1)

# Main Co-routine 
async def main():
    print("Starting")
    
    # Define STUN server configuration
    stun_server = RTCIceServer(urls=["stun:stun.l.google.com:19302"])

    # Create RTCConfiguration with STUN server
    config = RTCConfiguration(iceServers=[stun_server])

    peer_connection = RTCPeerConnection(configuration=config)

    @peer_connection.on("datachannel")
    def on_datachannel(channel):
        print(channel, "-", "created by remote party")
        channel.send("Hello From Answerer via RTC Datachannel")

        @channel.on("message")
        async def on_message(message):
            async with async_lock:
                received_chunks.append(message)

    resp = requests.get(SIGNALING_SERVER_URL + "/get_offer")

    print(resp.status_code)
    # print(resp.json())
    if resp.status_code == 200:
        data = resp.json()
        if data["type"] == "offer":
            rd = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
            await peer_connection.setRemoteDescription(rd)
            await peer_connection.setLocalDescription(await peer_connection.createAnswer())

            message = {"id": ID, "sdp": peer_connection.localDescription.sdp, "type": peer_connection.localDescription.type}
            r = requests.post(SIGNALING_SERVER_URL + '/answer', data=message)
            print(message)
            asyncio.create_task(process_messages())
            while True:
                print("Ready for Stuff")
                await asyncio.sleep(1)

asyncio.run(main())


# async def save_audio_to_file(track):
#     print(dir(track))
#     audio_data = await track.recv()
#     print(audio_data)

    # print(audio_data)
    # print(audio_data.format.name)
    # print(len(audio_data.to_ndarray()[0]))

    # print(dir(audio_data))

    # # Convert the AudioFrame to a numpy array
    # audio_array = audio_data.to_ndarray()

    # print(audio_data)
    # print(audio_data.is_corrupt)
    # # print(audio_data.pts)
    # print(audio_data.from_ndarray())
    # print(len(audio_data.layout.channels))
    # print(audio_data.rate)
    # print(audio_data.sample_rate)
    # print(audio_data.samples)
    # print(audio_data.to_ndarray)

# async def save_audio_to_file(track, peer_id):
#     try:
#         print("Receiving audio data...")
#         audio_data = await track.recv()
#         print("Audio data received",audio_data)
#         print(len(audio_data.to_ndarray()[0]))
#         print(audio_data.to_ndarray().astype(np.int16))
#         # Convert audio data to a NumPy array
#         audio_array = audio_data.to_ndarray()[0].astype(np.int16)

#         # Open a WAV file for writing
#         with wave.open('output.wav', 'wb') as wf:
#             # Set the parameters for the WAV file
#             wf.setnchannels(len(audio_data.layout.channels))  # Set number of channels
#             wf.setsampwidth(audio_array.dtype.itemsize)
#             wf.setframerate(audio_data.sample_rate)
#             wf.writeframes(audio_array.tobytes())
#             print("Successfully saved audio to output.wav")
#     except Exception as e:
#         print(f"Error saving audio: {e}")
