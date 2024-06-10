from fastapi import FastAPI, HTTPException, Form
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer, MediaStreamTrack
import json
import asyncio
from aiortc.contrib.media import MediaRecorder
import av
import io
from starlette.responses import StreamingResponse
import numpy as np
import wave
# import logging

app = FastAPI()
pcs = set()
# logging.basicConfig(level=logging.DEBUG)

# Global (for now; have to isolate buffer for each client) buffer to store audio data
audio_buffer = io.BytesIO()

# Create a child class to MediaRecorder class to record audio data to a buffer
class BufferMediaRecorder(MediaRecorder):
    def __init__(self, buffer, format="wav"):
        self.__container = av.open(buffer, format=format, mode="w")
        self.__tracks = {}
        super().__init__(buffer, format=format) 

    
# endpoint to accept offer from webrtc client for handshaking
@app.post("/offer")
async def offer_endpoint(sdp: str = Form(...), type: str = Form(...)):
    # logging.info(f"Received SDP: {sdp}, type: {type}")
    config = RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")])
    pc = RTCPeerConnection(configuration=config)
    pcs.add(pc)
    
    @pc.on("datachannel")
    def on_datachannel(channel):
        channel.send(f"Hello I'm server")

        @channel.on("message")
        async def on_message(message):
            print(message)
            # logging.info(f"Message received: {message}")

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
            # asyncio.ensure_future(save_audio())
            # await pc.close()

    try:
        offer_desc = RTCSessionDescription(sdp=sdp, type=type)
        await pc.setRemoteDescription(offer_desc)

        answer_desc = await pc.createAnswer()
        await pc.setLocalDescription(answer_desc)

        response = {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }

        print(response)
        # logging.info(f"Sending SDP answer: {response}")
        return response
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# end point to send audio back to the client
@app.get("/audio")
async def get_audio():
    audio_buffer.seek(0)
    # # Read the entire content of the buffer
    # audio_data = audio_buffer.read()
    
    # # Print the audio data on the console
    # print(audio_data)
    return StreamingResponse(audio_buffer, media_type="audio/wav")

# test endpoint to break data into chunks
# comment @app.get("/read-audio") and return statement
# and uncomment asyncio.ensure_future(save_audio()) to run the co-routine asynchronously
@app.get("/read-audio")
async def save_audio():
    chunk_size=4096
    audio_buffer.seek(0)
    data = []
    while True:
        # Read a chunk of bytes from the buffer
        chunk = audio_buffer.read(chunk_size)  # Adjust chunk size as needed
        # print(chunk)
        # Break the loop if no more data is available
        if not chunk:
            break

        # Append the chunk to the popped data
        data.append(chunk) 

    audio_data_bytes = b''.join(data)
    # audio_array = np.frombuffer(audio_data_bytes, dtype=np.int16)
    with wave.open('abhi.wav', 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(audio_data_bytes)

    return {"data":audio_buffer.read(),
            "index":audio_buffer.tell()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) # Increase the number of workers as needed and limit_max_requests
