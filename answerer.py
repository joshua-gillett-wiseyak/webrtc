import requests
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
import asyncio
import numpy as np
import wave

SIGNALING_SERVER_URL = 'http://localhost:9999'
ID = "answerer01"

async def save_audio_to_file(track):
    audio_data = await track.recv()
    # print(audio_data)
    # print(dir(audio_data))
    print(audio_data.pts)
    print(audio_data.from_ndarray)
    print(len(audio_data.layout.channels))
    print(audio_data.rate)
    print(audio_data.sample_rate)
    print(audio_data.samples)
    print(audio_data.to_ndarray)

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

async def main():
    print("Starting")
    
    # Define STUN server configuration
    stun_server = RTCIceServer(urls=["stun:stun.l.google.com:19302"])

    # Create RTCConfiguration with STUN server
    config = RTCConfiguration(iceServers=[stun_server])

    peer_connection = RTCPeerConnection(configuration=config)


    @peer_connection.on("track")
    def on_track(track):
        if track.kind == "audio":
            print("Received audio track")
            asyncio.ensure_future(save_audio_to_file(track))

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
            while True:
                print("Ready for Stuff")
                await asyncio.sleep(1)

asyncio.run(main())