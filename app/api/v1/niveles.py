from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.nivel import Nivel
from app.schemas.auth import TaskResponse
from app.core.queue import task_queue

router = APIRouter()


@router.get("/", response_model=List[dict])
async def read_niveles(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener lista de niveles"""
    from sqlalchemy import select

    result = await db.execute(select(Nivel).offset(skip).limit(limit))
    niveles = result.scalars().all()
    return [{"id": n.id, "nivel": n.nivel} for n in niveles]


@router.post("/", response_model=TaskResponse)
async def create_nivel_async(
    nivel_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear nivel de forma asíncrona"""
    task_id = await task_queue.add_task("create_nivel", nivel_data)
    return TaskResponse(
        task_id=task_id, message="Nivel agregado a la cola", status="pending"
    )
