from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
import json
import asyncio
import requests, aiohttp
import recorder
from aiortc.contrib.media import MediaPlayer, MediaStreamTrack

SIGNALING_SERVER_URL = 'http://localhost:9999'
ID = "offerer01"

async def main():
    print("Starting")

    # Define STUN server configuration
    stun_server = RTCIceServer(urls=["stun:stun.l.google.com:19302"]) # google's free stun server

    # Create RTCConfiguration with STUN server
    config = RTCConfiguration(iceServers=[stun_server])

    peer_connection = RTCPeerConnection(configuration=config)

    player = MediaPlayer('sample.wav')
    print(player.audio)
    peer_connection.addTrack(player.audio)

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