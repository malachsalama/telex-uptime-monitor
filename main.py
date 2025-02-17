from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import httpx
import asyncio

app = FastAPI()

class Setting(BaseModel):
    label: str
    type: str
    required: bool
    default: str

class MonitorPayload(BaseModel):
    channel_id: str
    return_url: str
    settings: List[Setting]

async def check_site_status(site: str) -> str:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(site, timeout=10)
            if response.status_code < 400:
                return None
            return f"{site} is down (status {response.status_code})"
    except Exception as e:
        return f"{site} check failed: {str(e)}"

async def monitor_task(payload: MonitorPayload):
    sites = [s.default for s in payload.settings if s.label.startswith("site")]
    results = await asyncio.gather(*(check_site_status(site) for site in sites))

    message = "\n".join([result for result in results if result is not None])

    # data follows telex webhook format. Your integration must call the return_url using this format
    data = {
        "message": message,
        "username": "Uptime Monitor",
        "event_name": "Uptime Check",
        "status": "error"
    }

    async with httpx.AsyncClient() as client:
        await client.post(payload.return_url, json=data)


@app.get("/integration.json")
def get_integration_json(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "data": {
            "descriptions": {
                "app_name": "Uptime Monitor",
                "app_description": "Monitors website uptime",
                "app_url": base_url,
                "app_logo": "https://i.imgur.com/lZqvffp.png",
                "background_color": "#fff"
            },
            "integration_type": "interval",
            "author": "Malach Salama",
            "settings": [
                {"label": "site-1", "type": "text", "required": True, "default": ""},
                {"label": "site-2", "type": "text", "required": True, "default": ""},
                {"label": "interval", "type": "text", "required": True, "default": "* * * * *"}
            ],
            "tick_url": f"{base_url}/tick"
        }
    }

@app.post("/tick", status_code=202)
def monitor(payload: MonitorPayload, background_tasks: BackgroundTasks):
    background_tasks.add_task(monitor_task, payload)
    return {"status": "accepted"}