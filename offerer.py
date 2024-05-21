from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
import asyncio
import requests
from aiortc.contrib.media import  MediaStreamTrack
import pyaudio

SIGNALING_SERVER_URL = 'http://localhost:9999' # endpoint of the signaling server to exchange sdp and ice
ID = "offerer01" # To represent peer that offers audio recording

# Define parameters for recording audio using PyAudio
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1 # Should be Mono for Silero VAD i.e CHANNELS=1
RATE = 44100
RECORD_SECONDS = 5

async def send_audio(stream, channel):
    print("* recording")
    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        if channel.readyState == "open":
            channel.send(data)
        await asyncio.sleep(0)  # Yield control to allow other tasks to run
    print("* done recording")
    channel.send('done')
    stream.stop_stream()
    stream.close()

# Define the main co-routine (Function)
async def main():
    print("Starting")

    # Define STUN server configuration
    stun_server = RTCIceServer(urls=["stun:stun.l.google.com:19302"]) # google's free stun server

    # Create RTCConfiguration with STUN server
    config = RTCConfiguration(iceServers=[stun_server])

    peer_connection = RTCPeerConnection(configuration=config)

    # Create a datachannel to pass the audio data to remote peer
    channel = peer_connection.createDataChannel("audio")

    audio_buffer=b'' # audio buffer
    # audio_buffer=[]

    # Record audio using PyAudio library
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    @channel.on("open")
    def on_open():
        print("channel opened")
        asyncio.create_task(send_audio(stream,channel))

    # @channel.on("message")
    # def on_message(message):
    #     print("Received via RTC Datachannel", message)

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
                    if not stream:
                        print("Ready for Streaming")
                    await asyncio.sleep(1)
            else:
                print("Wrong type")
            break

        print(resp.status_code)

asyncio.run(main())