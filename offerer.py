from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
import asyncio
import requests
from aiortc.contrib.media import  MediaStreamTrack
import pyaudio

SIGNALING_SERVER_URL = 'http://localhost:9999'
ID = "offerer01"

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
RECORD_SECONDS = 5

class MicrophoneAudioStream(MediaStreamTrack):
    kind = "audio"

    def __init__(self, audio_buffer):
        super().__init__()
        self.audio_buffer = audio_buffer

    async def recv(self):
        yield audio_buffer

async def main():
    print("Starting")

    # Define STUN server configuration
    stun_server = RTCIceServer(urls=["stun:stun.l.google.com:19302"]) # google's free stun server

    # Create RTCConfiguration with STUN server
    config = RTCConfiguration(iceServers=[stun_server])

    peer_connection = RTCPeerConnection(configuration=config)
    channel = peer_connection.createDataChannel("audio")

    audio_buffer=b''

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("* recording")

    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        audio_buffer += data

    print("* done recording")

    stream.stop_stream()
    stream.close()
    p.terminate()

    print("Starting streaming...")

    @channel.on("open")
    def on_open():
        print("channel openned")
        channel.send(audio_buffer)

    @channel.on("message")
    def on_message(message):
        print("Received via RTC Datachannel", message)

    # # Add recorded audio as a track to the peer connection
    # audio_track = MicrophoneAudioStream(audio_buffer)
    # audio_track = peer_connection.addTrack(audio_track)

    # send offer
    await peer_connection.setLocalDescription(await peer_connection.createOffer())
    message = {"id": ID, "sdp": peer_connection.localDescription.sdp, "type": peer_connection.localDescription.type}
    r = requests.post(SIGNALING_SERVER_URL + '/offer', data=message)
    print(r.status_code)
    
    #POLL FOR ANSWER
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