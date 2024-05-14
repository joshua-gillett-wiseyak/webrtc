from fastapi import FastAPI, Response, status, Form

app = FastAPI()

data = {}

@app.post('/offer', status_code=status.HTTP_200_OK)
async def offer(id: str = Form(...), sdp: str = Form(...), type: str = Form(...)):
    if type == "offer":
        data["offer"] = {"id" : id, "type" : type, "sdp" : sdp}
        return Response(status_code=status.HTTP_200_OK)
    else:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

@app.post('/answer', status_code=status.HTTP_200_OK)
async def answer(id: str = Form(...), sdp: str = Form(...), type: str = Form(...)):
    if type == "answer":
        data["answer"] = {"id" : id, "type" : type, "sdp" : sdp}
        return Response(status_code=status.HTTP_200_OK)
    else:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

@app.get('/get_offer', status_code=status.HTTP_200_OK)
async def get_offer():
    if "offer" in data:
        offer = data.pop("offer")
        return offer
    else:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

@app.get('/get_answer', status_code=status.HTTP_200_OK)
async def get_answer():
    if "answer" in data:
        answer = data.pop("answer")
        return answer
    else:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
