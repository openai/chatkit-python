from fastapi import FastAPI, Request
from chatkit.server import ChatKitServer

app = FastAPI()

# Update this if you have custom agent/workflow initialization!
server = ChatKitServer()

@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    return await server.chatkit_endpoint(request)
