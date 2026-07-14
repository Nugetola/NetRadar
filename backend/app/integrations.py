import asyncio
import json
import urllib.request
from .config import get_settings
from .notifications import _audit


async def create_external_ticket(payload: dict) -> bool:
    """Post an idempotency-friendly NetRadar ticket payload to IT-SUPPORT."""
    url = get_settings().it_support_webhook_url
    if not url:
        await _audit("IT_SUPPORT", "SKIPPED_NOT_CONFIGURED", payload)
        return False
    def send() -> int:
        request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "X-Source": "NetRadar"}, method="POST")
        with urllib.request.urlopen(request, timeout=15) as response: return response.status
    try:
        status = await asyncio.to_thread(send)
        outcome = "SENT" if 200 <= status < 300 else "FAILED"
        await _audit("IT_SUPPORT", outcome, {"ticket_id": payload["ticket_id"], "status": status})
        return outcome == "SENT"
    except OSError as exc:
        await _audit("IT_SUPPORT", "FAILED", {"ticket_id": payload["ticket_id"], "error": str(exc)})
        return False
