from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.nivel import Nivel
from app.models.materia import Materia
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_niveles(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de niveles con paginación inteligente (SÍNCRONO)"""

    def query_niveles(db: Session, offset: int, limit: int, **kwargs):
        niveles = db.query(Nivel).offset(offset).limit(limit).all()

        result = []
        for n in niveles:
            materias_count = db.query(Materia).filter(Materia.nivel_id == n.id).count()
            result.append(
                {
                    "id": n.id,
                    "nivel": n.nivel,
                    "semestre": f"Semestre {n.nivel}",
                    "materias_count": materias_count,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="niveles_list",
        query_function=query_niveles,
        query_params={},
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
    }


@router.get("/{nivel_id}")
def get_nivel(
    nivel_id: int,
    include_materias: bool = Query(False, description="Incluir materias del nivel"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver nivel específico con detalles"""
    nivel = db.query(Nivel).filter(Nivel.id == nivel_id).first()
    if not nivel:
        raise HTTPException(status_code=404, detail="Nivel no encontrado")

    nivel_data = {
        "id": nivel.id,
        "nivel": nivel.nivel,
        "semestre": f"Semestre {nivel.nivel}",
        "created_at": nivel.created_at.isoformat() if nivel.created_at else None,
    }

    # Estadísticas
    materias_count = db.query(Materia).filter(Materia.nivel_id == nivel.id).count()
    nivel_data["statistics"] = {
        "total_materias": materias_count,
    }

    if include_materias:
        materias = (
            db.query(Materia).filter(Materia.nivel_id == nivel.id).limit(20).all()
        )
        nivel_data["materias"] = [
            {
                "id": m.id,
                "sigla": m.sigla,
                "nombre": m.nombre,
                "creditos": m.creditos,
                "es_electiva": m.es_electiva,
            }
            for m in materias
        ]

    return nivel_data


@router.post("/")
def create_nivel(
    nivel_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear nivel"""
    try:
        required_fields = ["nivel"]
        missing_fields = [field for field in required_fields if field not in nivel_data]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que el nivel no exista
        existing = db.query(Nivel).filter(Nivel.nivel == nivel_data["nivel"]).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe el nivel {nivel_data['nivel']}",
            )

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_nivel",
            data=nivel_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Nivel en cola de procesamiento",
            "status": "pending",
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{nivel_id}")
def update_nivel(
    nivel_id: int,
    nivel_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Actualizar nivel"""
    nivel_data["id"] = nivel_id
    task_id = sync_thread_queue_manager.add_task(
        "update_nivel", nivel_data, priority=priority
    )
    return {"task_id": task_id, "message": "Actualización en cola", "status": "pending"}


@router.delete("/{nivel_id}")
def delete_nivel(
    nivel_id: int,
    force: bool = Query(False, description="Forzar eliminación"),
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Eliminar nivel"""
    task_id = sync_thread_queue_manager.add_task(
        "delete_nivel", {"id": nivel_id, "force": force}, priority=priority
    )
    return {"task_id": task_id, "message": "Eliminación en cola", "status": "pending"}
