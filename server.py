from fastapi import FastAPI, HTTPException, Form
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
import json
import asyncio
# import logging

app = FastAPI()
pcs = set()
# logging.basicConfig(level=logging.DEBUG)

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
