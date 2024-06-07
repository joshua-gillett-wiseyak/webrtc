from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer, MediaStreamTrack
import json
from aiortc.contrib.media import MediaRecorder
import asyncio
import io
import av
from starlette.responses import StreamingResponse

app = FastAPI()
clients = set()

# Global buffer to store audio data
audio_buffer = io.BytesIO()

class BufferMediaRecorder(MediaRecorder):
    def __init__(self, buffer, format="wav"):
        self.__container = av.open(buffer, format=format, mode="w")
        self.__tracks = {}
        super().__init__(buffer, format=format) 

async def rtcConnection(message):
    stun_server = RTCIceServer(urls=["stun:stun.l.google.com:19302"])
    config = RTCConfiguration(iceServers=[stun_server])
    pc = RTCPeerConnection(configuration=config)

    # Record the received audio to a file
    # recorder = MediaRecorder('received_audio.wav')
    # Record the received audio to the buffer
    recorder = BufferMediaRecorder(audio_buffer)

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

            # print(audio_buffer.tell())
            # print(audio_buffer)
    except WebSocketDisconnect:
        clients.remove(websocket)
        print("Client disconnected")
    finally:
        clients.remove(websocket)

@app.get("/audio")
async def get_audio():
    audio_buffer.seek(0)
    # # Read the entire content of the buffer
    # audio_data = audio_buffer.read()
    
    # # Print the audio data on the console
    # print(audio_data)
    return StreamingResponse(audio_buffer, media_type="audio/wav")

