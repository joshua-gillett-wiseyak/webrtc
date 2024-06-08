import asyncio
import json
import requests
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel, RTCConfiguration, RTCIceServer
import logging

# logging.basicConfig(level=logging.DEBUG)
async def run():
    config = RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")])
    pc = RTCPeerConnection(configuration=config)
    channel = pc.createDataChannel("chat")

    @channel.on("open")
    def on_open():
        print("Channel opened")
        channel.send('hello I\'m client')
        
    @channel.on("message")
    def on_message(message):
        print("Received via RTC Datachannel: ", message)


    await pc.setLocalDescription(await pc.createOffer())
    sdp_offer = {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }

    print(sdp_offer)

    try:
        response = requests.post("http://localhost:8000/offer", data=sdp_offer)
        print(response)
        if response.status_code == 200:
            answer = response.json()
            print(answer)
            answer_desc = RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
            await pc.setRemoteDescription(answer_desc)
            while True:
                print('waiting')
                await asyncio.sleep(5)
        else:
            pass
            logging.error("Failed to get SDP answer: %s", response.content)
    except Exception as e:
        print(e)
        # logging.error("Error during SDP offer/answer exchange: %s", e)
    
if __name__ == "__main__":
    asyncio.run(run())
