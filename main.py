from fastapi import FastAPI, Request
from chatkit.store import PostgresStore
from my_server import MyChatKitServer  # import your custom server class

app = FastAPI()
store = PostgresStore()  # Use PostgresStore as your backend

server = MyChatKitServer(store)

@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    result = await server.process(await request.body(), {})
    return result   # or, for streaming support, see further example below