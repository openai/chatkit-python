from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from postgres_store import PostgresStore
from my_server import MyChatKitServer  # import your custom server class
from pydantic import ValidationError
import json

app = FastAPI()
store = PostgresStore()  # This will read DATABASE_URL and connect
server = MyChatKitServer(store)

@app.get("/")
async def health_check():
    """Health check endpoint for monitoring and root access."""
    return {
        "status": "ok",
        "service": "BTS Tracker ChatKit Server",
        "endpoints": {
            "chatkit": "/chatkit (POST)",
            "health": "/ (GET)"
        }
    }

@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    try:
        # Get the raw body
        body = await request.body()

        # Try to parse as JSON for better error messages
        try:
            request_json = json.loads(body)

            # Check if 'type' field exists
            if not isinstance(request_json, dict) or 'type' not in request_json:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Invalid request format",
                        "message": "Request must be a JSON object with a 'type' field",
                        "details": "Expected format: {\"type\": \"threads/create\", \"params\": {...}}",
                        "valid_types": [
                            "threads/create",
                            "threads/add_user_message",
                            "threads/add_client_tool_output",
                            "threads/retry_after_item",
                            "threads/custom_action",
                            "threads/get_by_id",
                            "threads/list",
                            "items/list",
                            "items/feedback",
                            "attachments/create",
                            "attachments/delete",
                            "threads/update",
                            "threads/delete"
                        ]
                    }
                )
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid JSON",
                    "message": "Request body must be valid JSON"
                }
            )

        # Process the request through ChatKit server
        result = await server.process(body, {})
        return result

    except ValidationError as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Validation error",
                "message": str(e),
                "details": e.errors() if hasattr(e, 'errors') else None
            }
        )
    except Exception as e:
        # Log the error (in production, use proper logging)
        print(f"Error processing ChatKit request: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An error occurred while processing your request. Please check the request format and try again."
            }
        )