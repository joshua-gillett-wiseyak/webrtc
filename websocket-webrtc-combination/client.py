import asyncio
import websockets
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer, MediaStreamTrack
import asyncio
import json 
from aiortc.contrib.media import MediaPlayer
import sounddevice as sd

# WebSocket Server uri
uri = "ws://localhost:8765/ws"

async def rtcConnection():
    # Define STUN server configuration
    stun_server = RTCIceServer(urls=["stun:stun.l.google.com:19302"]) # google's free stun server
    config = RTCConfiguration(iceServers=[stun_server])
    pc = RTCPeerConnection(configuration=config)

    # Capture audio from the audiofile for now
    player = MediaPlayer('./audiotest.wav')
    audio_track = player.audio

    # Add audio track to the peer connection
    pc.addTrack(audio_track)

    await pc.setLocalDescription(await pc.createOffer())
    offer = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    return pc, offer


async def exchangeSDP():
    pc, offer=await rtcConnection()
    async with websockets.connect(uri) as websocket:
        print("Connected to the server.")
        
        await websocket.send(json.dumps(offer))
        
        response = await websocket.recv()
        response = json.loads(response)
        if response["type"] == "answer":
            rd = RTCSessionDescription(sdp=response["sdp"], type=response["type"])
            await pc.setRemoteDescription(rd)
            print(pc.remoteDescription)
            print("You can send mediastream object now")

            
asyncio.get_event_loop().run_until_complete(exchangeSDP())
asyncio.get_event_loop().run_forever()
