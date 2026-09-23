import os
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from azure.identity.aio import DefaultAzureCredential
from demo.parser import parse_agent_response, ParseError
from dotenv import load_dotenv

# Load env variables from root .env
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(title="NexDeal AI Demo Proxy")

# Attempt to load the endpoint; we don't crash on import if it's missing, just handle it at runtime.
ENDPOINT = os.environ.get("FOUNDRY_AGENT_RESPONSES_ENDPOINT", "").strip()

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

credential = DefaultAzureCredential()

class QuoteRequest(BaseModel):
    raw_request: str

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if not os.path.exists(html_path):
        return "<h1>Demo UI Not Found</h1><p>index.html is missing.</p>"
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/health")
async def health():
    return {"status": "ok", "endpoint_configured": bool(ENDPOINT)}

@app.post("/api/quote")
async def api_quote(req: QuoteRequest):
    if not ENDPOINT:
        raise HTTPException(status_code=500, detail="FOUNDRY_AGENT_RESPONSES_ENDPOINT is not configured.")

    try:
        # Get Azure access token (valid for AI Azure)
        token = await credential.get_token("https://ai.azure.com/.default")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to acquire Azure credential token.")

    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Construct the Responses API payload format (OpenAI Responses format)
    payload = {
        "input": req.raw_request,
        "store": True
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(ENDPOINT, json=payload, headers=headers, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            # We don't want to leak tokens, but we want to know what happened
            print("BACKEND ERROR BODY:", e.response.text)
            raise HTTPException(status_code=e.response.status_code, detail="Backend Error: The cloud Hosted Agent returned an error.")
        except Exception:
            raise HTTPException(status_code=500, detail="Communication error with Foundry.")

    # Extract the text string from the response
    try:
        outputs = data.get("output", [])
        if not outputs:
            raise ValueError("No output field in response")
        msg = outputs[0]
        content_list = msg.get("content", [])
        if not content_list:
            raise ValueError("No content array in response message")
        text_output = content_list[0].get("text", "")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to extract text from response payload.")

    # Deterministically parse the Python repr string into a structured JSON
    try:
        parsed_result = parse_agent_response(text_output)
    except ParseError:
        raise HTTPException(status_code=500, detail="Failed to parse backend response format.")

    return JSONResponse(content=parsed_result)
