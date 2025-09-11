from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.aula import Aula
from app.models.horario import Horario
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_aulas(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    modulo: Optional[str] = Query(None, description="Filtrar por módulo"),
    search: Optional[str] = Query(None, description="Buscar por módulo o aula"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de aulas con paginación inteligente (SÍNCRONO)"""

    def query_aulas(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Aula)

        if modulo:
            query = query.filter(Aula.modulo.ilike(f"%{modulo}%"))

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Aula.modulo.ilike(search_pattern)) | (Aula.aula.ilike(search_pattern))
            )

        aulas = query.offset(offset).limit(limit).all()

        result = []
        for a in aulas:
            horarios_count = db.query(Horario).filter(Horario.aula_id == a.id).count()
            result.append(
                {
                    "id": a.id,
                    "modulo": a.modulo,
                    "aula": a.aula,
                    "ubicacion": f"Módulo {a.modulo} - Aula {a.aula}",
                    "horarios_asignados": horarios_count,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="aulas_list",
        query_function=query_aulas,
        query_params={"modulo": modulo, "search": search},
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {"modulo": modulo, "search": search},
    }


@router.get("/{aula_id}")
def get_aula(
    aula_id: int,
    include_horarios: bool = Query(False, description="Incluir horarios del aula"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver aula específica con detalles"""
    aula = db.query(Aula).filter(Aula.id == aula_id).first()
    if not aula:
        raise HTTPException(status_code=404, detail="Aula no encontrada")

    aula_data = {
        "id": aula.id,
        "modulo": aula.modulo,
        "aula": aula.aula,
        "ubicacion": f"Módulo {aula.modulo} - Aula {aula.aula}",
        "created_at": aula.created_at.isoformat() if aula.created_at else None,
    }

    if include_horarios:
        horarios = db.query(Horario).filter(Horario.aula_id == aula.id).all()
        aula_data["horarios"] = [
            {
                "id": h.id,
                "dia": h.dia,
                "hora_inicio": str(h.hora_inicio),
                "hora_final": str(h.hora_final),
            }
            for h in horarios
        ]

    return aula_data


@router.post("/")
def create_aula(
    aula_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear aula"""
    try:
        required_fields = ["modulo", "aula"]
        missing_fields = [field for field in required_fields if field not in aula_data]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que no exista una combinación módulo-aula igual
        existing = (
            db.query(Aula)
            .filter(Aula.modulo == aula_data["modulo"], Aula.aula == aula_data["aula"])
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe el aula {aula_data['aula']} en el módulo {aula_data['modulo']}",
            )

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_aula",
            data=aula_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Aula en cola de procesamiento",
            "status": "pending",
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{aula_id}")
def update_aula(
    aula_id: int,
    aula_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Actualizar aula"""
    aula_data["id"] = aula_id
    task_id = sync_thread_queue_manager.add_task(
        "update_aula", aula_data, priority=priority
    )
    return {"task_id": task_id, "message": "Actualización en cola", "status": "pending"}


@router.delete("/{aula_id}")
def delete_aula(
    aula_id: int,
    force: bool = Query(False, description="Forzar eliminación"),
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Eliminar aula"""
    task_id = sync_thread_queue_manager.add_task(
        "delete_aula", {"id": aula_id, "force": force}, priority=priority
    )
    return {"task_id": task_id, "message": "Eliminación en cola", "status": "pending"}
