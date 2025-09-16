from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from typing import List, Dict, Any
from fastapi.responses import StreamingResponse
from app.api.deps import get_current_active_user
from app.core.redis_queue_monitor import redis_monitor
from app.core.security import verify_token  # usamos tu método
import asyncio
import json

router = APIRouter()


@router.get("/stats", tags=["Redis - Monitoring"])
def get_realtime_stats(current_user=Depends(get_current_active_user)):
    """Obtener estadísticas en tiempo real desde Redis"""
    return redis_monitor.get_current_stats()


@router.get("/events", tags=["Redis - Monitoring"])
def get_recent_events(
    limit: int = Query(50, ge=1, le=200),
    event_type: str = Query(None, description="Filtrar por tipo de evento"),
    current_user=Depends(get_current_active_user),
):
    """Obtener eventos recientes de la cola"""
    events = redis_monitor.get_recent_events(limit)

    # Filtrar por tipo de evento si se especifica
    if event_type:
        events = [e for e in events if e.get("event_type") == event_type]

    return {"events": events, "total": len(events), "filter": event_type}


@router.get("/workers", tags=["Redis - Monitoring"])
def get_active_workers(current_user=Depends(get_current_active_user)):
    """Obtener información de workers activos"""
    workers = redis_monitor.get_active_workers()
    return {"workers": workers, "total_active": len(workers)}


from fastapi import Request


@router.get("/stream/{event_type}", tags=["Redis - Monitoring"])
def get_event_stream(event_type: str, request: Request):
    from fastapi.responses import StreamingResponse
    import asyncio
    import json

    # Leer token del query param
    token = request.query_params.get("token")
    if not token or not verify_token(token):
        raise create_jwt_exception()

    async def event_generator():
        pubsub = redis_monitor.redis_client.pubsub()
        pubsub.subscribe(redis_monitor.QUEUE_EVENTS_CHANNEL)

        try:
            for message in pubsub.listen():
                if message["type"] == "message":
                    event_data = json.loads(message["data"])
                    if (
                        event_type == "all"
                        or event_data.get("event_type") == event_type
                    ):
                        yield f"data: {json.dumps(event_data)}\n\n"
                await asyncio.sleep(0.1)
        finally:
            pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
