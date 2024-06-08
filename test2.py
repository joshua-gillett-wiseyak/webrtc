import pyaudio
import asyncio
import requests
from aiortc import RTCIceServer, RTCPeerConnection, RTCSessionDescription, RTCConfiguration
from aiortc.contrib.media import MediaStreamTrack
from io import BytesIO

SIGNALING_SERVER_URL = 'http://localhost:9999'
ID = "offerer01"

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
RECORD_SECONDS = 5

class MicrophoneAudioStream(MediaStreamTrack):
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.frames = []

        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=FORMAT,
                                  channels=CHANNELS,
                                  rate=RATE,
                                  input=True,
                                  frames_per_buffer=CHUNK)

    async def recv(self):
        print("* recording")

        for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = self.stream.read(CHUNK)
            self.frames.append(data)
            yield data

        print("* done recording")

        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

        for frame in self.frames:
            yield frame

async def main():
 
    # Define STUN server configuration
    stun_server = RTCIceServer(urls=["stun:stun.l.google.com:19302"])

    # Create RTCConfiguration with STUN server
    config = RTCConfiguration(iceServers=[stun_server])

    # Create RTCPeerConnection
    peer_connection = RTCPeerConnection(configuration=config)

    # Add recorded audio as a track to the peer connection
    audio_stream = MicrophoneAudioStream()
    peer_connection.addTrack(audio_stream)

    # Send offer
    await peer_connection.setLocalDescription(await peer_connection.createOffer())
    offer = {"id": ID, "sdp": peer_connection.localDescription.sdp, "type": peer_connection.localDescription.type}
    r = requests.post(SIGNALING_SERVER_URL + '/offer', json=offer)
    print(r.status_code)
    
    # Poll for answer
    while True:
        resp = requests.get(SIGNALING_SERVER_URL + "/get_answer")
        if resp.status_code == 503:
            print("Answer not ready, trying again")
            await asyncio.sleep(1)
        elif resp.status_code == 200:
            data = resp.json()
            if data["type"] == "answer":
                rd = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                await peer_connection.setRemoteDescription(rd)
                print(peer_connection.remoteDescription)
                while True:
                    print("Ready for Stuff")
                    await asyncio.sleep(1)
            else:
                print("Wrong type")
            break

        print(resp.status_code)

asyncio.run(main())
