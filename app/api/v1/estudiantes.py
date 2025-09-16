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
    carrera_codigo: Optional[str] = Query(None, description="Filtrar por carrera"),
    search: Optional[str] = Query(None, description="Buscar por nombre, registro o CI"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener lista de estudiantes con paginación inteligente (VERSIÓN SÍNCRONA)"""

    def query_estudiantes(db: Session, offset: int, limit: int, **kwargs):
        """Función de consulta para paginación"""
        query = db.query(Estudiante)

        # Aplicar filtros
        if carrera_codigo:
            carrera = db.query(Carrera).filter(Carrera.codigo == carrera_codigo).first()
            if carrera:
                query = query.filter(Estudiante.carrera_id == carrera.id)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Estudiante.nombre.ilike(search_pattern))
                | (Estudiante.apellido.ilike(search_pattern))
                | (Estudiante.registro.ilike(search_pattern))
                | (Estudiante.ci.ilike(search_pattern))
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
        query_params={"carrera_codigo": carrera_codigo, "search": search},
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {"carrera_codigo": carrera_codigo, "search": search},
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


@router.get("/{registro}")
def get_estudiante(
    registro: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener estudiante específico por registro (VERSIÓN SÍNCRONA)"""
    estudiante = db.query(Estudiante).filter(Estudiante.registro == registro).first()

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
    db: Session = Depends(get_db),
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
            "carrera_codigo",  # Cambio: usar carrera_codigo en lugar de carrera_id
        ]
        missing_fields = [
            field for field in required_fields if field not in estudiante_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que la carrera existe
        carrera = (
            db.query(Carrera)
            .filter(Carrera.codigo == estudiante_data["carrera_codigo"])
            .first()
        )
        if not carrera:
            raise HTTPException(
                status_code=400,
                detail=f"No existe carrera con código '{estudiante_data['carrera_codigo']}'",
            )

        # Verificar que no exista el registro
        existing_registro = (
            db.query(Estudiante)
            .filter(Estudiante.registro == estudiante_data["registro"])
            .first()
        )
        if existing_registro:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un estudiante con el registro '{estudiante_data['registro']}'",
            )

        # Verificar que no exista el CI
        existing_ci = (
            db.query(Estudiante).filter(Estudiante.ci == estudiante_data["ci"]).first()
        )
        if existing_ci:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un estudiante con el CI '{estudiante_data['ci']}'",
            )

        # Convertir carrera_codigo a carrera_id para el procesamiento
        estudiante_data["carrera_id"] = carrera.id

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


@router.put("/{registro}")
def update_estudiante(
    registro: str,
    estudiante_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Actualizar estudiante (procesamiento síncrono con rollback)"""
    try:
        # Verificar que existe
        existing_student = (
            db.query(Estudiante).filter(Estudiante.registro == registro).first()
        )

        if not existing_student:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")

        # Verificar registro único si se está cambiando
        if (
            "registro" in estudiante_data
            and estudiante_data["registro"] != existing_student.registro
        ):
            duplicate_registro = (
                db.query(Estudiante)
                .filter(
                    Estudiante.registro == estudiante_data["registro"],
                    Estudiante.id != existing_student.id,
                )
                .first()
            )
            if duplicate_registro:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe un estudiante con el registro '{estudiante_data['registro']}'",
                )

        # Verificar CI único si se está cambiando
        if "ci" in estudiante_data and estudiante_data["ci"] != existing_student.ci:
            duplicate_ci = (
                db.query(Estudiante)
                .filter(
                    Estudiante.ci == estudiante_data["ci"],
                    Estudiante.id != existing_student.id,
                )
                .first()
            )
            if duplicate_ci:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe un estudiante con el CI '{estudiante_data['ci']}'",
                )

        # Verificar carrera si se está cambiando
        if "carrera_codigo" in estudiante_data:
            carrera = (
                db.query(Carrera)
                .filter(Carrera.codigo == estudiante_data["carrera_codigo"])
                .first()
            )
            if not carrera:
                raise HTTPException(
                    status_code=400,
                    detail=f"No existe carrera con código '{estudiante_data['carrera_codigo']}'",
                )
            estudiante_data["carrera_id"] = carrera.id

        # Agregar registro original a los datos
        estudiante_data["registro_original"] = registro

        # Configurar rollback con estado original
        rollback_data = {
            "operation": "update",
            "table": "estudiantes",
            "registro_original": registro,
            "original_data": {
                "registro": existing_student.registro,
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
            "registro": registro,
            "check_status": f"/queue/tasks/{task_id}",
            "rollback_available": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{registro}")
def delete_estudiante(
    registro: str,
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Eliminar estudiante (procesamiento síncrono)"""
    try:
        # Verificar que existe
        estudiante = (
            db.query(Estudiante).filter(Estudiante.registro == registro).first()
        )
        if not estudiante:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")

        task_id = sync_thread_queue_manager.add_task(
            task_type="delete_estudiante",
            data={"registro": registro},
            priority=priority,
            max_retries=2,
        )

        return {
            "task_id": task_id,
            "message": "Eliminación en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "registro": registro,
            "check_status": f"/queue/tasks/{task_id}",
            "warning": "Esta operación no se puede deshacer",
        }

    except HTTPException:
        raise
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
                    "carrera_codigo",
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
