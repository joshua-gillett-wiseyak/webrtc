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


buffer_lock = asyncio.Lock() # buffer_lock to avoid race condition
app = FastAPI() # Initialize the FastAPI 
pcs = set() # set of peer connections
client_buffer={} # {'c1':'io.BytesIO()', 'c2':'io.BytesIO()', ...} client buffer mapping dictionary to store streaming audio data into buffer
client_chunks={} # {'c1':[], 'c2':[], ...} client - list mapping dictionary to read from the buffer and check if audio is available in the chunks
# logging.basicConfig(level=logging.DEBUG)


# Create a child class to MediaRecorder class to record audio data to a buffer
class BufferMediaRecorder(MediaRecorder):
    def __init__(self, buffer, format="wav"):
        self.__container = av.open(buffer, format=format, mode="w") 
        self.__tracks = {} 
        super().__init__(buffer, format=format) 

    
# endpoint to accept offer from webrtc client for handshaking
@app.post("/offer")
async def offer_endpoint(sdp: str = Form(...), type: str = Form(...), client_id: int = Form(...)):
    # logging.info(f"Received SDP: {sdp}, type: {type}")
    config = RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]) # make use of google's stun server
    pc = RTCPeerConnection(configuration=config) # pass the config to configuration to make use of stun server
    pcs.add(client_id) # add peer connection to set of peer connections

    # Separate out buffer for each peer connection
    audio_buffer = io.BytesIO()
    client_buffer[client_id]=audio_buffer
    client_chunks[client_id]=[]

    # event handler for data channel
    @pc.on("datachannel")
    def on_datachannel(channel):
        channel.send(f"Hello I'm server")

        @channel.on("message")
        async def on_message(message):
            print(message)
            # logging.info(f"Message received: {message}")

    # By default, records the received audio to a file
    # example: recorder = MediaRecorder('received_audio.wav')
    # To record the received audio to the buffer, Implement a child class to the main MediaRecorder class
    recorder = BufferMediaRecorder(audio_buffer)

    # event handler for tracks (audio/video)
    @pc.on("track")
    def on_track(track: MediaStreamTrack):
        print(f"Track {track.kind} received")
        if track.kind == "audio":
            recorder.addTrack(track)
            # asyncio.ensure_future(recorder.start())
            asyncio.ensure_future(start_recorder(recorder))
            asyncio.ensure_future(read_buffer_chunks(client_id))

        @track.on("ended")
        async def on_ended():
            print(f"Track {track.kind} ended")
            await recorder.stop()
            # asyncio.ensure_future(save_audio())
            # await pc.close()

    # Clean-up function for disconnection
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        # print(pc.connectionState)
        if pc.connectionState in ["failed", "closed", "disconnected"]:
            print(f"Connection state is {pc.connectionState}, cleaning up")
            pcs.discard(client_id)
            del client_buffer[client_id]
            del client_chunks[client_id]

    # start writing to buffer with buffer_lock
    async def start_recorder(recorder): 
        async with buffer_lock:
            await recorder.start()
    
    async def read_buffer_chunks(client_id):
        while True:
            await asyncio.sleep(1)  # adjust the sleep time based on your requirements
            async with buffer_lock:
                audio_buffer = client_buffer[client_id]
                audio_buffer.seek(0, io.SEEK_END)
                size = audio_buffer.tell()
                audio_buffer.seek(0, io.SEEK_SET)
                chunk = audio_buffer.read(size)
                if chunk:
                    client_chunks[client_id].append(chunk)
                audio_buffer.seek(0)
                audio_buffer.truncate()

    # Handshake with the clients to make WebRTC Connections
    try:
        offer_desc = RTCSessionDescription(sdp=sdp, type=type)
        await pc.setRemoteDescription(offer_desc)

        answer_desc = await pc.createAnswer()
        await pc.setLocalDescription(answer_desc)

        response = {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }

        # print(response)
        # logging.info(f"Sending SDP answer: {response}")
        return response # respond with the sdp information of the server
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# end point to send audio back to the client (for now just streaming the audio back to the client)
# endpoint: /audio?client_id=<client_id>
@app.get("/audio")
async def get_audio(client_id: int):
    print(client_buffer)
    audio_buffer = client_buffer[client_id]
    audio_buffer.seek(0) # seek the audio buffer to the start of the audio
    # # Read the entire content of the buffer
    # audio_data = audio_buffer.read()
    
    # # Print the audio data on the console
    # print(audio_data)
    return StreamingResponse(audio_buffer, media_type="audio/wav") 


# test endpoint to break data into chunks
# comment @app.get("/read-audio") and return statement
# and uncomment asyncio.ensure_future(save_audio()) to run the co-routine asynchronously
@app.get("/read-audio")
async def save_audio(client_id: int):
    # audio_buffer = client_buffer[client_id]
    # chunk_size=4096
    # audio_buffer.seek(0)
    # data = []
    # while True:
    #     # Read a chunk of bytes from the buffer
    #     chunk = audio_buffer.read(chunk_size)  # Adjust chunk size as needed
    #     # print(chunk)
    #     # Break the loop if no more data is available
    #     if not chunk:
    #         break

    #     # Append the chunk to the popped data
    #     data.append(chunk) 

    # audio_data_bytes = b''.join(data)
    # # audio_array = np.frombuffer(audio_data_bytes, dtype=np.int16)
    # with wave.open('abhi.wav', 'wb') as wf:
    #     wf.setnchannels(2)
    #     wf.setsampwidth(2)
    #     wf.setframerate(44100)
    #     wf.writeframes(audio_data_bytes)
    chunks=client_chunks[client_id]
    # print(chunks)
    return {"index":len(chunks)}
    # return {"data":audio_buffer.read(),
    #         "index":audio_buffer.tell()}

@app.get("/")
def getClients():
    return {
        "clients": list(pcs),  # Convert set to list for JSON serialization
        "client_buffer": list(client_buffer.keys()),  # Get all client IDs in the buffer
        "client_chunks": {client_id: len(chunks) for client_id, chunks in client_chunks.items()}  # Get all client chunks and their sizes
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) # Increase the number of workers as needed and limit_max_requests
