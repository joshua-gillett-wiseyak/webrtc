from fastapi import FastAPI, HTTPException, Form
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer, MediaStreamTrack, AudioStreamTrack
import json
import asyncio
from aiortc.contrib.media import MediaRecorder, MediaPlayer
import av
import io
from starlette.responses import StreamingResponse
import numpy as np
import wave
import requests
import torch
import torchaudio
import matplotlib.pyplot as plt
# import logging

app = FastAPI() # Initialize the FastAPI 

pcs = set() # set of peer connections
client_buffer={} # {'c1':'io.BytesIO()', 'c2':'io.BytesIO()', ...} client buffer mapping dictionary to store streaming audio data into buffer
client_chunks={} # {'c1':[], 'c2':[], ...} client - list mapping dictionary to read from the buffer and check if audio is available in the chunks
client_datachannels={} # {'c1': channelC1, 'c2':channelC2, ...} client - datachannels mapping dictionary to make channel accessible outside of the event handler
# logging.basicConfig(level=logging.DEBUG)

buffer_lock = asyncio.Lock() # buffer_lock to avoid race condition

# loading model for vad
model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                              model='silero_vad',
                              force_reload=True,
                              onnx=False)
SAMPLE_RATE = 16000
SILENCE_TIME = 2 # 2 seconds
FRAMES_PER_CHUNK = 1024
SILENCE_SAMPLES = SAMPLE_RATE * SILENCE_TIME

speech_threshold = 0
speech_audio = torch.empty(0)
silence_audio = torch.empty(0)
prob_data = []
silence_found = False

resample = torchaudio.transforms.Resample(orig_freq = 44100, new_freq = 16000)

def VAD_from_chunk_input(chunk, threshold_weight = 0.9):
    global speech_threshold
    global speech_audio
    global silence_audio
    global prob_data
    global silence_found

    np_chunk = np.frombuffer(chunk, dtype = np.int16)
    np_chunk = np_chunk.astype(np.float32) / 32768.0
    print("np_chunk", type(np_chunk), np_chunk.shape)
    chunk_audio = torch.from_numpy(np_chunk)
    print("chunk_audio", type(chunk_audio), np_chunk.size)
    chunk_audio = resample(chunk_audio)
    # consider meaning into one channel here
    print("chunk_audio resample", type(chunk_audio), np_chunk.size)
    # if chunk_audio.shape[0] < FRAMES_PER_CHUNK:
    #     print("Chunk small", chunk_audio.shape[0])
    # Find prob of speech for using silero-vad
    speech_prob = model(chunk_audio, SAMPLE_RATE).item()
    prob_data.append(speech_prob)

    if speech_prob >= speech_threshold:
        speech_audio = torch.cat((speech_audio, chunk_audio), dim=0)
        silence_audio = torch.empty(0)
    else:
        silence_audio = torch.cat((silence_audio, chunk_audio), dim=0)
        if silence_audio.shape[0] >= SILENCE_SAMPLES:
            if not silence_found:
                speech_unsq = torch.unsqueeze(speech_audio, dim=0)
                torchaudio.save("outputSpeech.wav", speech_unsq, SAMPLE_RATE)
                print("Speech data saved at outputSpeech.wav", )
                raise SystemExit
            silence_found = True
            print("found silence")
        else:
            speech_audio = torch.cat((speech_audio, chunk_audio), dim=0)
    
    # adaptive thresholding
    # this should in theory allow for silence at the beginning of audio
    speech_threshold = threshold_weight * max([i**2 for i in prob_data]) + (1 - threshold_weight) * min([i**2 for i in prob_data])

    # pass the spoken data to LLM
    # pass speech_audio

    #for testing


# Create a child class to MediaRecorder class to record audio data to a buffer
class BufferMediaRecorder(MediaRecorder):
    """
    A subclass of MediaRecorder that supports using BytesIO buffer as output.
    
    :param buffer: The buffer containing audio data as a BytesIO object.
    """
    def __init__(self, buffer, format="wav"):
        self.__container = av.open(buffer, format=format, mode="w") 
        self.__tracks = {} 
        super().__init__(buffer, format=format) 


# endpoint to accept offer from webrtc client for handshaking
@app.post("/offer")
async def offer_endpoint(sdp: str = Form(...), type: str = Form(...), client_id: str = Form(...)):
    # logging.info(f"Received SDP: {sdp}, type: {type}")
    config = RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]) # make use of google's stun server
    pc = RTCPeerConnection(configuration=config) # pass the config to configuration to make use of stun server
    pcs.add(client_id) # add peer connection to set of peer connections

    # Separate out buffer for each peer connection
    audio_buffer = io.BytesIO()
    client_buffer[client_id]=audio_buffer
    client_chunks[client_id]=[]

    # By default, records the received audio to a file
    # example: recorder = MediaRecorder('received_audio.wav')
    # To record the received audio to the buffer, Implement a child class to the main MediaRecorder class
    recorder = BufferMediaRecorder(audio_buffer)

    # event handler for data channel
    @pc.on("datachannel")
    def on_datachannel(channel):
        client_datachannels[client_id]=channel # to make datachannel accessible outside of this scope
        channel.send(f"Hello I'm server")

        @channel.on("message")
        async def on_message(message):
            print(message)
            # logging.info(f"Message received: {message}")


    # event handler for tracks (audio/video)
    @pc.on("track")
    def on_track(track: MediaStreamTrack):
        print(f"Track {track.kind} received. Make sure to use .start() to start recording to buffer")
        if track.kind == "audio":
            recorder.addTrack(track)
            # audio_sender=pc.addTrack(MediaPlayer('./serverToClient.wav').audio)
            audio_sender=pc.addTrack(AudioStreamTrack())
            # asyncio.ensure_future(recorder.start())
            asyncio.ensure_future(start_recorder(recorder))
            asyncio.ensure_future(read_buffer_chunks(audio_sender,client_id))

            
            # pc.addTrack(AudioStreamTrack())
            
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
    
    async def read_buffer_chunks(audio_sender,client_id):
        await asyncio.sleep(10)
        audio_sender.replaceTrack(MediaPlayer('./serverToClient.wav').audio)

        while True:
            await asyncio.sleep(0.1)  # adjust the sleep time based on your requirements
            async with buffer_lock:
                audio_buffer = client_buffer[client_id]
                audio_buffer.seek(0, io.SEEK_END)
                size = audio_buffer.tell()
                print("chunk size wh")
                audio_buffer.seek(0, io.SEEK_SET)
                chunk = audio_buffer.read(size)
                if chunk:
                    client_chunks[client_id].append(chunk)
                audio_buffer.seek(0)
                audio_buffer.truncate()
                
                VAD_from_chunk_input(chunk)

                # get the client's datachannel 
                dc=client_datachannels[client_id]
                dc.send("Iteration inside While Loop")

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
        
        print(response)
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
## @app.get("/read-audio")
## async def save_audio(client_id: int):
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
    ## chunks=client_chunks[client_id]
    # print(chunks)
    ## return {"index":len(chunks)}
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
    uvicorn.run(app, host="localhost", port=8000) # Increase the number of workers as needed and limit_max_requests
