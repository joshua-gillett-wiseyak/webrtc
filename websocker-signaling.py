from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Dict

app = FastAPI()

clients: Dict[str, WebSocket] = {}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    clients[client_id] = websocket
    try:
        while True:
            data = await websocket.receive_text()
            for client in clients:
                if client != client_id:
                    await clients[client].send_text(data)
    except WebSocketDisconnect:
        del clients[client_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("signalingserver:app", host="0.0.0.0", port=8000, log_level="info")