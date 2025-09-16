from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.detalle import Detalle
from app.models.grupo import Grupo
from app.models.materia import Materia
from app.models.docente import Docente
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_detalles(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    grupo_id: Optional[int] = Query(None, description="Filtrar por grupo"),
    fecha: Optional[str] = Query(None, description="Filtrar por fecha (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de detalles con paginación inteligente (SÍNCRONO)"""

    def query_detalles(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Detalle)

        if grupo_id:
            query = query.filter(Detalle.grupo_id == grupo_id)

        if fecha:
            from datetime import datetime

            try:
                fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
                query = query.filter(Detalle.fecha == fecha_obj)
            except ValueError:
                pass  # Ignorar fecha inválida

        detalles = query.offset(offset).limit(limit).all()

        result = []
        for d in detalles:
            grupo = db.query(Grupo).filter(Grupo.id == d.grupo_id).first()
            materia = None
            docente = None

            if grupo:
                materia = (
                    db.query(Materia).filter(Materia.id == grupo.materia_id).first()
                )
                docente = (
                    db.query(Docente).filter(Docente.id == grupo.docente_id).first()
                )

            result.append(
                {
                    "id": d.id,
                    "fecha": d.fecha.isoformat() if d.fecha else None,
                    "hora": str(d.hora) if d.hora else None,
                    "grupo": (
                        {
                            "id": grupo.id,
                            "descripcion": grupo.descripcion,
                        }
                        if grupo
                        else None
                    ),
                    "materia": (
                        {
                            "id": materia.id,
                            "sigla": materia.sigla,
                            "nombre": materia.nombre,
                        }
                        if materia
                        else None
                    ),
                    "docente": (
                        {
                            "id": docente.id,
                            "nombre_completo": f"{docente.nombre} {docente.apellido}",
                        }
                        if docente
                        else None
                    ),
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="detalles_list",
        query_function=query_detalles,
        query_params={"grupo_id": grupo_id, "fecha": fecha},
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {"grupo_id": grupo_id, "fecha": fecha},
    }


@router.get("/{detalle_id}")
def get_detalle(
    detalle_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver detalle específico con información completa"""
    detalle = db.query(Detalle).filter(Detalle.id == detalle_id).first()
    if not detalle:
        raise HTTPException(status_code=404, detail="Detalle no encontrado")

    # Obtener información relacionada
    grupo = db.query(Grupo).filter(Grupo.id == detalle.grupo_id).first()
    materia = None
    docente = None

    if grupo:
        materia = db.query(Materia).filter(Materia.id == grupo.materia_id).first()
        docente = db.query(Docente).filter(Docente.id == grupo.docente_id).first()

    return {
        "id": detalle.id,
        "fecha": detalle.fecha.isoformat() if detalle.fecha else None,
        "hora": str(detalle.hora) if detalle.hora else None,
        "grupo": (
            {
                "id": grupo.id,
                "descripcion": grupo.descripcion,
                "horario_id": grupo.horario_id,
                "gestion_id": grupo.gestion_id,
            }
            if grupo
            else None
        ),
        "materia": (
            {
                "id": materia.id,
                "sigla": materia.sigla,
                "nombre": materia.nombre,
                "creditos": materia.creditos,
            }
            if materia
            else None
        ),
        "docente": (
            {
                "id": docente.id,
                "nombre": docente.nombre,
                "apellido": docente.apellido,
                "nombre_completo": f"{docente.nombre} {docente.apellido}",
            }
            if docente
            else None
        ),
        "created_at": detalle.created_at.isoformat() if detalle.created_at else None,
        "updated_at": detalle.updated_at.isoformat() if detalle.updated_at else None,
    }


@router.post("/")
def create_detalle(
    detalle_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear detalle"""
    try:
        required_fields = ["fecha", "hora", "grupo_id"]
        missing_fields = [
            field for field in required_fields if field not in detalle_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que el grupo existe
        grupo = db.query(Grupo).filter(Grupo.id == detalle_data["grupo_id"]).first()
        if not grupo:
            raise HTTPException(status_code=400, detail="Grupo no encontrado")

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_detalle",
            data=detalle_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Detalle en cola de procesamiento",
            "status": "pending",
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{detalle_id}")
def update_detalle(
    detalle_id: int,
    detalle_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Actualizar detalle"""
    detalle_data["id"] = detalle_id
    task_id = sync_thread_queue_manager.add_task(
        "update_detalle", detalle_data, priority=priority
    )
    return {"task_id": task_id, "message": "Actualización en cola", "status": "pending"}


@router.delete("/{detalle_id}")
def delete_detalle(
    detalle_id: int,
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Eliminar detalle"""
    task_id = sync_thread_queue_manager.add_task(
        "delete_detalle", {"id": detalle_id}, priority=priority
    )
    return {"task_id": task_id, "message": "Eliminación en cola", "status": "pending"}


@router.get("/grupo/{grupo_id}")
def get_detalles_by_grupo(
    grupo_id: int,
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener detalles de un grupo específico"""
    # Verificar que el grupo existe
    grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")

    def query_detalles_grupo(db: Session, offset: int, limit: int, **kwargs):
        detalles = (
            db.query(Detalle)
            .filter(Detalle.grupo_id == grupo_id)
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            {
                "id": d.id,
                "fecha": d.fecha.isoformat() if d.fecha else None,
                "hora": str(d.hora) if d.hora else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in detalles
        ]

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint=f"detalles_grupo_{grupo_id}",
        query_function=query_detalles_grupo,
        query_params={},
        page_size=page_size,
    )

    return {
        "grupo": {
            "id": grupo.id,
            "descripcion": grupo.descripcion,
        },
        "detalles": results,
        "pagination": metadata,
    }


@router.get("/fecha/{fecha}")
def get_detalles_by_fecha(
    fecha: str,  # Formato: YYYY-MM-DD
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener todos los detalles de una fecha específica"""
    from datetime import datetime

    try:
        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD"
        )

    detalles = db.query(Detalle).filter(Detalle.fecha == fecha_obj).all()

    result = []
    for d in detalles:
        grupo = db.query(Grupo).filter(Grupo.id == d.grupo_id).first()
        materia = None
        docente = None

        if grupo:
            materia = db.query(Materia).filter(Materia.id == grupo.materia_id).first()
            docente = db.query(Docente).filter(Docente.id == grupo.docente_id).first()

        result.append(
            {
                "id": d.id,
                "hora": str(d.hora) if d.hora else None,
                "grupo": (
                    {
                        "id": grupo.id,
                        "descripcion": grupo.descripcion,
                    }
                    if grupo
                    else None
                ),
                "materia_sigla": materia.sigla if materia else None,
                "docente_nombre": (
                    f"{docente.nombre} {docente.apellido}" if docente else None
                ),
            }
        )

    return {
        "fecha": fecha,
        "total_detalles": len(result),
        "detalles": result,
    }
