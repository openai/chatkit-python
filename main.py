from fastapi import FastAPI, Request
from chatkit.store import SQLiteStore
from my_server import MyChatKitServer  # import your class

app = FastAPI()
store = SQLiteStore("sqlite.db")

server = MyChatKitServer(store)

@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    result = await server.process(await request.body(), {})
    return result