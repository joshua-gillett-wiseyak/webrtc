from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer, MediaStreamTrack
import json
from aiortc.contrib.media import MediaRecorder
import asyncio

app = FastAPI()
clients = set()

async def rtcConnection(message):
    stun_server = RTCIceServer(urls=["stun:stun.l.google.com:19302"])
    config = RTCConfiguration(iceServers=[stun_server])
    pc = RTCPeerConnection(configuration=config)

    # Record the received audio to a file
    recorder = MediaRecorder('received_audio.wav')

    @pc.on("track")
    def on_track(track: MediaStreamTrack):
        print(f"Track {track.kind} received")
        if track.kind == "audio":
            recorder.addTrack(track)
            asyncio.ensure_future(recorder.start())

        @track.on("ended")
        async def on_ended():
            print(f"Track {track.kind} ended")
            await recorder.stop()
            await pc.close()

    await pc.setRemoteDescription(RTCSessionDescription(sdp=message["sdp"], type=message["type"]))
    await pc.setLocalDescription(await pc.createAnswer())
    answer = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    return json.dumps(answer)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        async for message in websocket.iter_text():
            answer = await rtcConnection(json.loads(message))
            print(answer)
            await websocket.send_text(answer)
    except WebSocketDisconnect:
        clients.remove(websocket)
        print("Client disconnected")
    finally:
        clients.remove(websocket)

