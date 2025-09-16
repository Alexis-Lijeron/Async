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
                (Aula.modulo.ilike(search_pattern))
                | (Aula.aula.ilike(search_pattern))
                | (Aula.codigo_aula.ilike(search_pattern))
            )

        aulas = query.offset(offset).limit(limit).all()

        result = []
        for a in aulas:
            horarios_count = db.query(Horario).filter(Horario.aula_id == a.id).count()
            result.append(
                {
                    "id": a.id,
                    "codigo_aula": a.codigo_aula,
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


@router.get("/{codigo_aula}")
def get_aula(
    codigo_aula: str,
    include_horarios: bool = Query(False, description="Incluir horarios del aula"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver aula específica con detalles"""
    aula = db.query(Aula).filter(Aula.codigo_aula == codigo_aula).first()
    if not aula:
        raise HTTPException(status_code=404, detail="Aula no encontrada")

    aula_data = {
        "id": aula.id,
        "codigo_aula": aula.codigo_aula,
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
                "codigo_horario": h.codigo_horario,
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
        required_fields = ["codigo_aula", "modulo", "aula"]
        missing_fields = [field for field in required_fields if field not in aula_data]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que no exista el código de aula
        existing = (
            db.query(Aula).filter(Aula.codigo_aula == aula_data["codigo_aula"]).first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un aula con el código '{aula_data['codigo_aula']}'",
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


@router.put("/{codigo_aula}")
def update_aula(
    codigo_aula: str,
    aula_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Actualizar aula"""
    # Verificar que existe
    existing_aula = db.query(Aula).filter(Aula.codigo_aula == codigo_aula).first()
    if not existing_aula:
        raise HTTPException(status_code=404, detail="Aula no encontrada")

    aula_data["codigo_aula"] = codigo_aula
    task_id = sync_thread_queue_manager.add_task(
        "update_aula", aula_data, priority=priority
    )
    return {"task_id": task_id, "message": "Actualización en cola", "status": "pending"}


@router.delete("/{codigo_aula}")
def delete_aula(
    codigo_aula: str,
    force: bool = Query(False, description="Forzar eliminación"),
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Eliminar aula"""
    # Verificar que existe
    aula = db.query(Aula).filter(Aula.codigo_aula == codigo_aula).first()
    if not aula:
        raise HTTPException(status_code=404, detail="Aula no encontrada")

    task_id = sync_thread_queue_manager.add_task(
        "delete_aula", {"codigo_aula": codigo_aula, "force": force}, priority=priority
    )
    return {"task_id": task_id, "message": "Eliminación en cola", "status": "pending"}
