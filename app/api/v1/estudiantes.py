from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.estudiante import Estudiante
from app.models.carrera import Carrera
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_estudiantes(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    carrera_id: Optional[int] = Query(None, description="Filtrar por carrera"),
    search: Optional[str] = Query(None, description="Buscar por nombre o registro"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener lista de estudiantes con paginación inteligente (VERSIÓN SÍNCRONA)"""

    def query_estudiantes(db: Session, offset: int, limit: int, **kwargs):
        """Función de consulta para paginación"""
        query = db.query(Estudiante)

        # Aplicar filtros
        if carrera_id:
            query = query.filter(Estudiante.carrera_id == carrera_id)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Estudiante.nombre.ilike(search_pattern))
                | (Estudiante.apellido.ilike(search_pattern))
                | (Estudiante.registro.ilike(search_pattern))
            )

        estudiantes = query.offset(offset).limit(limit).all()

        # Obtener información de carrera
        estudiantes_data = []
        for e in estudiantes:
            carrera = db.query(Carrera).filter(Carrera.id == e.carrera_id).first()

            estudiantes_data.append(
                {
                    "id": e.id,
                    "registro": e.registro,
                    "nombre": e.nombre,
                    "apellido": e.apellido,
                    "ci": e.ci,
                    "carrera": (
                        {
                            "id": carrera.id,
                            "codigo": carrera.codigo,
                            "nombre": carrera.nombre,
                        }
                        if carrera
                        else None
                    ),
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
            )

        return estudiantes_data

    # Generar session_id si no se proporciona
    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    # Usar paginación inteligente
    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="estudiantes_list",
        query_function=query_estudiantes,
        query_params={"carrera_id": carrera_id, "search": search},
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {"carrera_id": carrera_id, "search": search},
        "instructions": {
            "next_page": f"Usa el mismo session_id '{metadata['session_id']}' para obtener más resultados",
            "reset": f"Para reiniciar usa DELETE /queue/pagination/sessions/{metadata['session_id']}",
        },
    }


@router.get("/me")
def get_estudiante_actual(current_user=Depends(get_current_active_user)):
    """Mi información completa (VERSIÓN SÍNCRONA)"""
    from app.config.database import SessionLocal

    with SessionLocal() as db:
        carrera = (
            db.query(Carrera).filter(Carrera.id == current_user.carrera_id).first()
        )

        return {
            "id": current_user.id,
            "registro": current_user.registro,
            "nombre": current_user.nombre,
            "apellido": current_user.apellido,
            "ci": current_user.ci,
            "carrera": (
                {"id": carrera.id, "codigo": carrera.codigo, "nombre": carrera.nombre}
                if carrera
                else None
            ),
            "created_at": (
                current_user.created_at.isoformat() if current_user.created_at else None
            ),
        }


@router.get("/{estudiante_id}")
def get_estudiante(
    estudiante_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener estudiante específico (VERSIÓN SÍNCRONA)"""
    estudiante = db.query(Estudiante).filter(Estudiante.id == estudiante_id).first()

    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    # Obtener carrera
    carrera = db.query(Carrera).filter(Carrera.id == estudiante.carrera_id).first()

    return {
        "id": estudiante.id,
        "registro": estudiante.registro,
        "nombre": estudiante.nombre,
        "apellido": estudiante.apellido,
        "ci": estudiante.ci,
        "carrera": (
            {"id": carrera.id, "codigo": carrera.codigo, "nombre": carrera.nombre}
            if carrera
            else None
        ),
        "created_at": (
            estudiante.created_at.isoformat() if estudiante.created_at else None
        ),
        "updated_at": (
            estudiante.updated_at.isoformat() if estudiante.updated_at else None
        ),
    }


@router.post("/")
def create_estudiante(
    estudiante_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Crear estudiante (procesamiento síncrono)"""
    try:
        # Validar campos requeridos
        required_fields = [
            "registro",
            "nombre",
            "apellido",
            "ci",
            "contraseña",
            "carrera_id",
        ]
        missing_fields = [
            field for field in required_fields if field not in estudiante_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Configurar rollback
        rollback_data = {
            "operation": "create",
            "table": "estudiantes",
            "created_by": current_user.id,
        }

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_estudiante",
            data=estudiante_data,
            priority=priority,
            max_retries=3,
            rollback_data=rollback_data,
        )

        return {
            "task_id": task_id,
            "message": "Estudiante en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "check_status": f"/queue/tasks/{task_id}",
            "estimated_processing": "1-5 segundos",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{estudiante_id}")
def update_estudiante(
    estudiante_id: int,
    estudiante_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Actualizar estudiante (procesamiento síncrono con rollback)"""
    try:
        # Verificar que existe
        from app.config.database import SessionLocal

        with SessionLocal() as db:
            existing_student = (
                db.query(Estudiante).filter(Estudiante.id == estudiante_id).first()
            )

            if not existing_student:
                raise HTTPException(status_code=404, detail="Estudiante no encontrado")

        # Agregar ID a los datos
        estudiante_data["id"] = estudiante_id

        # Configurar rollback con estado original
        rollback_data = {
            "operation": "update",
            "table": "estudiantes",
            "record_id": estudiante_id,
            "original_data": {
                "nombre": existing_student.nombre,
                "apellido": existing_student.apellido,
                "ci": existing_student.ci,
                "carrera_id": existing_student.carrera_id,
            },
            "updated_by": current_user.id,
        }

        task_id = sync_thread_queue_manager.add_task(
            task_type="update_estudiante",
            data=estudiante_data,
            priority=priority,
            max_retries=3,
            rollback_data=rollback_data,
        )

        return {
            "task_id": task_id,
            "message": "Actualización en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "estudiante_id": estudiante_id,
            "check_status": f"/queue/tasks/{task_id}",
            "rollback_available": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{estudiante_id}")
def delete_estudiante(
    estudiante_id: int,
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Eliminar estudiante (procesamiento síncrono)"""
    try:
        task_id = sync_thread_queue_manager.add_task(
            task_type="delete_estudiante",
            data={"id": estudiante_id},
            priority=priority,
            max_retries=2,
        )

        return {
            "task_id": task_id,
            "message": "Eliminación en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "estudiante_id": estudiante_id,
            "check_status": f"/queue/tasks/{task_id}",
            "warning": "Esta operación no se puede deshacer",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk")
def create_bulk_estudiantes(
    estudiantes_data: list,
    priority: int = Query(6, ge=1, le=10, description="Prioridad de las tareas"),
    current_user=Depends(get_current_active_user),
):
    """Crear múltiples estudiantes en lote (VERSIÓN SÍNCRONA)"""
    try:
        if not estudiantes_data:
            raise HTTPException(status_code=400, detail="Lista vacía")

        if len(estudiantes_data) > 50:
            raise HTTPException(status_code=400, detail="Máximo 50 estudiantes")

        task_ids = []
        errors = []

        for i, estudiante_data in enumerate(estudiantes_data):
            try:
                required_fields = [
                    "registro",
                    "nombre",
                    "apellido",
                    "ci",
                    "contraseña",
                    "carrera_id",
                ]
                missing_fields = [
                    field for field in required_fields if field not in estudiante_data
                ]

                if missing_fields:
                    errors.append(
                        f"Estudiante {i+1}: Campos faltantes: {', '.join(missing_fields)}"
                    )
                    continue

                rollback_data = {
                    "operation": "create",
                    "table": "estudiantes",
                    "batch_index": i,
                    "created_by": current_user.id,
                }

                task_id = sync_thread_queue_manager.add_task(
                    task_type="create_estudiante",
                    data=estudiante_data,
                    priority=priority + i,
                    rollback_data=rollback_data,
                )

                task_ids.append(
                    {
                        "task_id": task_id,
                        "batch_index": i,
                        "registro": estudiante_data.get("registro"),
                    }
                )

            except Exception as e:
                errors.append(f"Estudiante {i+1}: {str(e)}")

        return {
            "success": True,
            "tasks_created": len(task_ids),
            "tasks_failed": len(errors),
            "total_requested": len(estudiantes_data),
            "task_ids": task_ids,
            "errors": errors,
            "check_all_status": "/queue/tasks?task_type=create_estudiante&status=pending",
            "estimated_completion": f"{len(task_ids) * 2} segundos",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
