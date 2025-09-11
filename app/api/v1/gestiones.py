from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.gestion import Gestion
from app.models.grupo import Grupo
from app.models.inscripcion import Inscripcion
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_gestiones(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    año: Optional[int] = Query(None, description="Filtrar por año"),
    semestre: Optional[int] = Query(None, description="Filtrar por semestre"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de gestiones con paginación inteligente (SÍNCRONO)"""

    def query_gestiones(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Gestion)

        if año:
            query = query.filter(Gestion.año == año)
        if semestre:
            query = query.filter(Gestion.semestre == semestre)

        gestiones = query.offset(offset).limit(limit).all()

        result = []
        for g in gestiones:
            grupos_count = db.query(Grupo).filter(Grupo.gestion_id == g.id).count()
            inscripciones_count = (
                db.query(Inscripcion).filter(Inscripcion.gestion_id == g.id).count()
            )

            result.append(
                {
                    "id": g.id,
                    "semestre": g.semestre,
                    "año": g.año,
                    "descripcion": f"Semestre {g.semestre} - {g.año}",
                    "grupos_count": grupos_count,
                    "inscripciones_count": inscripciones_count,
                    "esta_activa": True,  # Aquí podrías implementar lógica para determinar si está activa
                    "created_at": g.created_at.isoformat() if g.created_at else None,
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="gestiones_list",
        query_function=query_gestiones,
        query_params={"año": año, "semestre": semestre},
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {"año": año, "semestre": semestre},
    }


@router.get("/{gestion_id}")
def get_gestion(
    gestion_id: int,
    include_grupos: bool = Query(False, description="Incluir grupos de la gestión"),
    include_statistics: bool = Query(True, description="Incluir estadísticas"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver gestión específica con detalles"""
    gestion = db.query(Gestion).filter(Gestion.id == gestion_id).first()
    if not gestion:
        raise HTTPException(status_code=404, detail="Gestión no encontrada")

    gestion_data = {
        "id": gestion.id,
        "semestre": gestion.semestre,
        "año": gestion.año,
        "descripcion": f"Semestre {gestion.semestre} - {gestion.año}",
        "created_at": gestion.created_at.isoformat() if gestion.created_at else None,
    }

    if include_statistics:
        grupos_count = db.query(Grupo).filter(Grupo.gestion_id == gestion.id).count()
        inscripciones_count = (
            db.query(Inscripcion).filter(Inscripcion.gestion_id == gestion.id).count()
        )

        gestion_data["statistics"] = {
            "total_grupos": grupos_count,
            "total_inscripciones": inscripciones_count,
        }

    if include_grupos:
        grupos = db.query(Grupo).filter(Grupo.gestion_id == gestion.id).limit(20).all()
        from app.models.materia import Materia
        from app.models.docente import Docente

        grupos_info = []
        for grupo in grupos:
            materia = db.query(Materia).filter(Materia.id == grupo.materia_id).first()
            docente = db.query(Docente).filter(Docente.id == grupo.docente_id).first()
            grupos_info.append(
                {
                    "id": grupo.id,
                    "descripcion": grupo.descripcion,
                    "materia_sigla": materia.sigla if materia else None,
                    "docente": (
                        f"{docente.nombre} {docente.apellido}" if docente else None
                    ),
                }
            )

        gestion_data["grupos"] = grupos_info

    return gestion_data


@router.post("/")
def create_gestion(
    gestion_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear gestión"""
    try:
        required_fields = ["semestre", "año"]
        missing_fields = [
            field for field in required_fields if field not in gestion_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Validar semestre
        if gestion_data["semestre"] not in [1, 2, 3, 4]:
            raise HTTPException(
                status_code=400,
                detail="El semestre debe ser 1, 2, 3 o 4",
            )

        # Verificar que no exista la misma gestión
        existing = (
            db.query(Gestion)
            .filter(
                Gestion.semestre == gestion_data["semestre"],
                Gestion.año == gestion_data["año"],
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe la gestión Semestre {gestion_data['semestre']} - {gestion_data['año']}",
            )

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_gestion",
            data=gestion_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Gestión en cola de procesamiento",
            "status": "pending",
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{gestion_id}")
def update_gestion(
    gestion_id: int,
    gestion_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Actualizar gestión"""
    gestion_data["id"] = gestion_id
    task_id = sync_thread_queue_manager.add_task(
        "update_gestion", gestion_data, priority=priority
    )
    return {"task_id": task_id, "message": "Actualización en cola", "status": "pending"}


@router.delete("/{gestion_id}")
def delete_gestion(
    gestion_id: int,
    force: bool = Query(False, description="Forzar eliminación"),
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Eliminar gestión"""
    task_id = sync_thread_queue_manager.add_task(
        "delete_gestion", {"id": gestion_id, "force": force}, priority=priority
    )
    return {"task_id": task_id, "message": "Eliminación en cola", "status": "pending"}
