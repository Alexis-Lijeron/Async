from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.plan_estudio import PlanEstudio
from app.models.carrera import Carrera
from app.models.materia import Materia
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_planes_estudio(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    carrera_id: Optional[int] = Query(None, description="Filtrar por carrera"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de planes de estudio con paginación inteligente (SÍNCRONO)"""

    def query_planes_estudio(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(PlanEstudio)

        if carrera_id:
            query = query.filter(PlanEstudio.carrera_id == carrera_id)

        planes = query.offset(offset).limit(limit).all()

        result = []
        for p in planes:
            carrera = db.query(Carrera).filter(Carrera.id == p.carrera_id).first()
            materias_count = (
                db.query(Materia).filter(Materia.plan_estudio_id == p.id).count()
            )

            result.append(
                {
                    "id": p.id,
                    "codigo": p.codigo,
                    "plan": p.plan,
                    "cant_semestre": p.cant_semestre,
                    "carrera": (
                        {
                            "id": carrera.id,
                            "codigo": carrera.codigo,
                            "nombre": carrera.nombre,
                        }
                        if carrera
                        else None
                    ),
                    "materias_count": materias_count,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="planes_estudio_list",
        query_function=query_planes_estudio,
        query_params={"carrera_id": carrera_id},
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {"carrera_id": carrera_id},
    }


@router.get("/{plan_id}")
def get_plan_estudio(
    plan_id: int,
    include_materias: bool = Query(False, description="Incluir materias del plan"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver plan de estudio específico con detalles"""
    plan = db.query(PlanEstudio).filter(PlanEstudio.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan de estudio no encontrado")

    carrera = db.query(Carrera).filter(Carrera.id == plan.carrera_id).first()

    plan_data = {
        "id": plan.id,
        "codigo": plan.codigo,
        "plan": plan.plan,
        "cant_semestre": plan.cant_semestre,
        "carrera": (
            {
                "id": carrera.id,
                "codigo": carrera.codigo,
                "nombre": carrera.nombre,
            }
            if carrera
            else None
        ),
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }

    # Estadísticas
    materias_count = (
        db.query(Materia).filter(Materia.plan_estudio_id == plan.id).count()
    )
    plan_data["statistics"] = {
        "total_materias": materias_count,
    }

    if include_materias:
        materias = (
            db.query(Materia).filter(Materia.plan_estudio_id == plan.id).limit(50).all()
        )
        plan_data["materias"] = [
            {
                "id": m.id,
                "sigla": m.sigla,
                "nombre": m.nombre,
                "creditos": m.creditos,
                "es_electiva": m.es_electiva,
                "nivel_id": m.nivel_id,
            }
            for m in materias
        ]

    return plan_data


@router.post("/")
def create_plan_estudio(
    plan_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear plan de estudio"""
    try:
        required_fields = ["codigo", "plan", "cant_semestre", "carrera_id"]
        missing_fields = [field for field in required_fields if field not in plan_data]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que el código no exista
        existing = (
            db.query(PlanEstudio)
            .filter(PlanEstudio.codigo == plan_data["codigo"])
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un plan de estudio con el código '{plan_data['codigo']}'",
            )

        # Verificar que la carrera existe
        carrera = (
            db.query(Carrera).filter(Carrera.id == plan_data["carrera_id"]).first()
        )
        if not carrera:
            raise HTTPException(status_code=400, detail="Carrera no encontrada")

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_plan_estudio",
            data=plan_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Plan de estudio en cola de procesamiento",
            "status": "pending",
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{plan_id}")
def update_plan_estudio(
    plan_id: int,
    plan_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Actualizar plan de estudio"""
    plan_data["id"] = plan_id
    task_id = sync_thread_queue_manager.add_task(
        "update_plan_estudio", plan_data, priority=priority
    )
    return {"task_id": task_id, "message": "Actualización en cola", "status": "pending"}


@router.delete("/{plan_id}")
def delete_plan_estudio(
    plan_id: int,
    force: bool = Query(False, description="Forzar eliminación"),
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Eliminar plan de estudio"""
    task_id = sync_thread_queue_manager.add_task(
        "delete_plan_estudio", {"id": plan_id, "force": force}, priority=priority
    )
    return {"task_id": task_id, "message": "Eliminación en cola", "status": "pending"}


@router.get("/carrera/{carrera_id}")
def get_planes_by_carrera(
    carrera_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener planes de estudio por carrera"""
    carrera = db.query(Carrera).filter(Carrera.id == carrera_id).first()
    if not carrera:
        raise HTTPException(status_code=404, detail="Carrera no encontrada")

    planes = db.query(PlanEstudio).filter(PlanEstudio.carrera_id == carrera_id).all()

    return {
        "carrera": {
            "id": carrera.id,
            "codigo": carrera.codigo,
            "nombre": carrera.nombre,
        },
        "planes": [
            {
                "id": p.id,
                "codigo": p.codigo,
                "plan": p.plan,
                "cant_semestre": p.cant_semestre,
            }
            for p in planes
        ],
    }
