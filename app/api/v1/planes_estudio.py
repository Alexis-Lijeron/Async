from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.plan_estudio import PlanEstudio
from app.schemas.auth import TaskResponse
from app.core.queue import task_queue

router = APIRouter()


@router.get("/", response_model=List[dict])
async def read_planes_estudio(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener lista de planes de estudio"""
    from sqlalchemy import select

    result = await db.execute(select(PlanEstudio).offset(skip).limit(limit))
    planes = result.scalars().all()
    return [
        {
            "id": p.id,
            "codigo": p.codigo,
            "plan": p.plan,
            "cant_semestre": p.cant_semestre,
        }
        for p in planes
    ]


@router.post("/", response_model=TaskResponse)
async def create_plan_estudio_async(
    plan_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear plan de estudio de forma asíncrona"""
    task_id = await task_queue.add_task("create_plan_estudio", plan_data)
    return TaskResponse(
        task_id=task_id, message="Plan de estudio agregado a la cola", status="pending"
    )
