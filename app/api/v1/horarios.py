from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.horario import Horario
from app.models.aula import Aula
from app.models.grupo import Grupo
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_horarios(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    dia: Optional[str] = Query(None, description="Filtrar por día"),
    aula_id: Optional[int] = Query(None, description="Filtrar por aula"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de horarios con paginación inteligente (SÍNCRONO)"""

    def query_horarios(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Horario)

        if dia:
            query = query.filter(Horario.dia.ilike(f"%{dia}%"))
        if aula_id:
            query = query.filter(Horario.aula_id == aula_id)

        horarios = query.offset(offset).limit(limit).all()

        result = []
        for h in horarios:
            aula = db.query(Aula).filter(Aula.id == h.aula_id).first()
            grupos_count = db.query(Grupo).filter(Grupo.horario_id == h.id).count()

            result.append(
                {
                    "id": h.id,
                    "dia": h.dia,
                    "hora_inicio": str(h.hora_inicio),
                    "hora_final": str(h.hora_final),
                    "duracion_horas": str(h.hora_final.hour - h.hora_inicio.hour),
                    "aula": (
                        {
                            "id": aula.id,
                            "modulo": aula.modulo,
                            "aula": aula.aula,
                            "ubicacion": f"Módulo {aula.modulo} - Aula {aula.aula}",
                        }
                        if aula
                        else None
                    ),
                    "grupos_asignados": grupos_count,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="horarios_list",
        query_function=query_horarios,
        query_params={"dia": dia, "aula_id": aula_id},
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {"dia": dia, "aula_id": aula_id},
    }


@router.get("/{horario_id}")
def get_horario(
    horario_id: int,
    include_grupos: bool = Query(
        False, description="Incluir grupos que usan este horario"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver horario específico con detalles"""
    horario = db.query(Horario).filter(Horario.id == horario_id).first()
    if not horario:
        raise HTTPException(status_code=404, detail="Horario no encontrado")

    aula = db.query(Aula).filter(Aula.id == horario.aula_id).first()

    horario_data = {
        "id": horario.id,
        "dia": horario.dia,
        "hora_inicio": str(horario.hora_inicio),
        "hora_final": str(horario.hora_final),
        "duracion_horas": horario.hora_final.hour - horario.hora_inicio.hour,
        "aula": (
            {
                "id": aula.id,
                "modulo": aula.modulo,
                "aula": aula.aula,
                "ubicacion": f"Módulo {aula.modulo} - Aula {aula.aula}",
            }
            if aula
            else None
        ),
        "created_at": horario.created_at.isoformat() if horario.created_at else None,
    }

    if include_grupos:
        grupos = db.query(Grupo).filter(Grupo.horario_id == horario.id).limit(20).all()
        from app.models.materia import Materia
        from app.models.docente import Docente

        grupos_info = []
        for g in grupos:
            materia = db.query(Materia).filter(Materia.id == g.materia_id).first()
            docente = db.query(Docente).filter(Docente.id == g.docente_id).first()
            grupos_info.append(
                {
                    "id": g.id,
                    "descripcion": g.descripcion,
                    "materia_sigla": materia.sigla if materia else None,
                    "docente": (
                        f"{docente.nombre} {docente.apellido}" if docente else None
                    ),
                }
            )

        horario_data["grupos"] = grupos_info

    return horario_data


@router.post("/")
def create_horario(
    horario_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear horario"""
    try:
        required_fields = ["dia", "hora_inicio", "hora_final", "aula_id"]
        missing_fields = [
            field for field in required_fields if field not in horario_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que el aula existe
        if not db.query(Aula).filter(Aula.id == horario_data["aula_id"]).first():
            raise HTTPException(status_code=400, detail="Aula no encontrada")

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_horario",
            data=horario_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Horario en cola de procesamiento",
            "status": "pending",
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{horario_id}")
def update_horario(
    horario_id: int,
    horario_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Actualizar horario"""
    horario_data["id"] = horario_id
    task_id = sync_thread_queue_manager.add_task(
        "update_horario", horario_data, priority=priority
    )
    return {"task_id": task_id, "message": "Actualización en cola", "status": "pending"}


@router.delete("/{horario_id}")
def delete_horario(
    horario_id: int,
    force: bool = Query(False, description="Forzar eliminación"),
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Eliminar horario"""
    task_id = sync_thread_queue_manager.add_task(
        "delete_horario", {"id": horario_id, "force": force}, priority=priority
    )
    return {"task_id": task_id, "message": "Eliminación en cola", "status": "pending"}
