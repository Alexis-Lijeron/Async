from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.carrera import Carrera
from app.models.estudiante import Estudiante
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_carreras(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    search: Optional[str] = Query(None, description="Buscar por código o nombre"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de carreras con paginación inteligente (SÍNCRONO)"""

    def query_carreras(db: Session, offset: int, limit: int, **kwargs):
        """Función de consulta para paginación"""
        query = db.query(Carrera)

        # Aplicar filtros
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Carrera.codigo.ilike(search_pattern))
                | (Carrera.nombre.ilike(search_pattern))
            )

        carreras = query.offset(offset).limit(limit).all()

        # Obtener cantidad de estudiantes por carrera
        carreras_data = []
        for c in carreras:
            estudiantes_count = (
                db.query(Estudiante).filter(Estudiante.carrera_id == c.id).count()
            )
            carreras_data.append(
                {
                    "id": c.id,
                    "codigo": c.codigo,
                    "nombre": c.nombre,
                    "estudiantes_count": estudiantes_count,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
            )

        return carreras_data

    # Generar session_id si no se proporciona
    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    # Usar paginación inteligente
    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="carreras_list",
        query_function=query_carreras,
        query_params={"search": search},
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {"search": search},
        "instructions": {
            "next_page": f"Usa el mismo session_id '{metadata['session_id']}' para obtener más resultados",
            "reset": f"Para reiniciar usa DELETE /queue/pagination/sessions/{metadata['session_id']}",
        },
    }


@router.get("/{codigo}")
def get_carrera(
    codigo: str,
    include_estudiantes: bool = Query(
        False, description="Incluir lista de estudiantes"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver carrera específica con detalles (SÍNCRONO)"""
    carrera = db.query(Carrera).filter(Carrera.codigo == codigo).first()
    if not carrera:
        raise HTTPException(status_code=404, detail="Carrera no encontrada")

    # Datos básicos
    carrera_data = {
        "id": carrera.id,
        "codigo": carrera.codigo,
        "nombre": carrera.nombre,
        "created_at": carrera.created_at.isoformat() if carrera.created_at else None,
        "updated_at": carrera.updated_at.isoformat() if carrera.updated_at else None,
    }

    # Estadísticas
    estudiantes_count = (
        db.query(Estudiante).filter(Estudiante.carrera_id == carrera.id).count()
    )
    carrera_data["statistics"] = {
        "total_estudiantes": estudiantes_count,
    }

    # Incluir estudiantes si se solicita
    if include_estudiantes:
        estudiantes = (
            db.query(Estudiante)
            .filter(Estudiante.carrera_id == carrera.id)
            .limit(50)  # Límite para evitar sobrecarga
            .all()
        )
        carrera_data["estudiantes"] = [
            {
                "id": e.id,
                "registro": e.registro,
                "nombre": e.nombre,
                "apellido": e.apellido,
            }
            for e in estudiantes
        ]

    return carrera_data


@router.post("/")
def create_carrera(
    carrera_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear carrera (procesamiento síncrono)"""
    try:
        # Validar campos requeridos
        required_fields = ["codigo", "nombre"]
        missing_fields = [
            field for field in required_fields if field not in carrera_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que el código no exista
        existing = (
            db.query(Carrera).filter(Carrera.codigo == carrera_data["codigo"]).first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe una carrera con el código '{carrera_data['codigo']}'",
            )

        # Configurar rollback
        rollback_data = {
            "operation": "create",
            "table": "carreras",
            "created_by": current_user.id,
        }

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_carrera",
            data=carrera_data,
            priority=priority,
            max_retries=3,
            rollback_data=rollback_data,
        )

        return {
            "task_id": task_id,
            "message": "Carrera en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "check_status": f"/queue/tasks/{task_id}",
            "estimated_processing": "1-3 segundos",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{codigo}")
def update_carrera(
    codigo: str,
    carrera_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Actualizar carrera (procesamiento síncrono con rollback)"""
    try:
        # Verificar que existe
        existing_carrera = db.query(Carrera).filter(Carrera.codigo == codigo).first()
        if not existing_carrera:
            raise HTTPException(status_code=404, detail="Carrera no encontrada")

        # Verificar código único si se está cambiando
        if (
            "codigo" in carrera_data
            and carrera_data["codigo"] != existing_carrera.codigo
        ):
            codigo_exists = (
                db.query(Carrera)
                .filter(
                    Carrera.codigo == carrera_data["codigo"],
                    Carrera.id != existing_carrera.id,
                )
                .first()
            )
            if codigo_exists:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe una carrera con el código '{carrera_data['codigo']}'",
                )

        # Agregar código original a los datos
        carrera_data["codigo_original"] = codigo

        # Configurar rollback con estado original
        rollback_data = {
            "operation": "update",
            "table": "carreras",
            "codigo_original": codigo,
            "original_data": {
                "codigo": existing_carrera.codigo,
                "nombre": existing_carrera.nombre,
            },
            "updated_by": current_user.id,
        }

        task_id = sync_thread_queue_manager.add_task(
            task_type="update_carrera",
            data=carrera_data,
            priority=priority,
            max_retries=3,
            rollback_data=rollback_data,
        )

        return {
            "task_id": task_id,
            "message": "Actualización en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "codigo": codigo,
            "check_status": f"/queue/tasks/{task_id}",
            "rollback_available": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{codigo}")
def delete_carrera(
    codigo: str,
    force: bool = Query(
        False, description="Forzar eliminación aunque tenga estudiantes"
    ),
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Eliminar carrera"""
    try:
        # Verificar que existe
        carrera = db.query(Carrera).filter(Carrera.codigo == codigo).first()
        if not carrera:
            raise HTTPException(status_code=404, detail="Carrera no encontrada")

        # Verificar si tiene estudiantes
        estudiantes_count = (
            db.query(Estudiante).filter(Estudiante.carrera_id == carrera.id).count()
        )
        if estudiantes_count > 0 and not force:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede eliminar la carrera porque tiene {estudiantes_count} estudiantes asociados. Use force=true para forzar la eliminación.",
            )

        task_id = sync_thread_queue_manager.add_task(
            task_type="delete_carrera",
            data={"codigo": codigo, "force": force},
            priority=priority,
            max_retries=2,
        )

        return {
            "task_id": task_id,
            "message": "Eliminación en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "codigo": codigo,
            "students_affected": estudiantes_count if force else 0,
            "check_status": f"/queue/tasks/{task_id}",
            "warning": "Esta operación no se puede deshacer"
            + (
                f" y afectará a {estudiantes_count} estudiantes"
                if force and estudiantes_count > 0
                else ""
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{codigo}/estudiantes")
def get_carrera_estudiantes(
    codigo: str,
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    search: Optional[str] = Query(None, description="Buscar estudiantes"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener estudiantes de una carrera específica con paginación"""
    # Verificar que la carrera existe
    carrera = db.query(Carrera).filter(Carrera.codigo == codigo).first()
    if not carrera:
        raise HTTPException(status_code=404, detail="Carrera no encontrada")

    def query_estudiantes_carrera(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Estudiante).filter(Estudiante.carrera_id == carrera.id)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Estudiante.nombre.ilike(search_pattern))
                | (Estudiante.apellido.ilike(search_pattern))
                | (Estudiante.registro.ilike(search_pattern))
            )

        estudiantes = query.offset(offset).limit(limit).all()
        return [
            {
                "id": e.id,
                "registro": e.registro,
                "nombre": e.nombre,
                "apellido": e.apellido,
                "ci": e.ci,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in estudiantes
        ]

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint=f"carrera_{codigo}_estudiantes",
        query_function=query_estudiantes_carrera,
        query_params={"search": search},
        page_size=page_size,
    )

    return {
        "carrera": {
            "id": carrera.id,
            "codigo": carrera.codigo,
            "nombre": carrera.nombre,
        },
        "estudiantes": results,
        "pagination": metadata,
    }
