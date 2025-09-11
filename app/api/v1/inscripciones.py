from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.inscripcion import Inscripcion
from app.models.grupo import Grupo
from app.models.materia import Materia
from app.models.estudiante import Estudiante
from app.models.gestion import Gestion
from app.models.docente import Docente
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_inscripciones(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    estudiante_id: Optional[int] = Query(None, description="Filtrar por estudiante"),
    grupo_id: Optional[int] = Query(None, description="Filtrar por grupo"),
    gestion_id: Optional[int] = Query(None, description="Filtrar por gestión"),
    semestre: Optional[int] = Query(None, description="Filtrar por semestre"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de inscripciones con paginación inteligente (SÍNCRONO)"""

    def query_inscripciones(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Inscripcion)

        if estudiante_id:
            query = query.filter(Inscripcion.estudiante_id == estudiante_id)
        if grupo_id:
            query = query.filter(Inscripcion.grupo_id == grupo_id)
        if gestion_id:
            query = query.filter(Inscripcion.gestion_id == gestion_id)
        if semestre:
            query = query.filter(Inscripcion.semestre == semestre)

        inscripciones = query.offset(offset).limit(limit).all()

        result = []
        for i in inscripciones:
            estudiante = (
                db.query(Estudiante).filter(Estudiante.id == i.estudiante_id).first()
            )
            grupo = db.query(Grupo).filter(Grupo.id == i.grupo_id).first()
            gestion = db.query(Gestion).filter(Gestion.id == i.gestion_id).first()

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
                    "id": i.id,
                    "semestre": i.semestre,
                    "estudiante": (
                        {
                            "id": estudiante.id,
                            "registro": estudiante.registro,
                            "nombre": estudiante.nombre,
                            "apellido": estudiante.apellido,
                            "nombre_completo": f"{estudiante.nombre} {estudiante.apellido}",
                        }
                        if estudiante
                        else None
                    ),
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
                            "creditos": materia.creditos,
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
                    "gestion": (
                        {
                            "id": gestion.id,
                            "semestre": gestion.semestre,
                            "año": gestion.año,
                            "descripcion": f"SEM {gestion.semestre}/{gestion.año}",
                        }
                        if gestion
                        else None
                    ),
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="inscripciones_list",
        query_function=query_inscripciones,
        query_params={
            "estudiante_id": estudiante_id,
            "grupo_id": grupo_id,
            "gestion_id": gestion_id,
            "semestre": semestre,
        },
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {
            "estudiante_id": estudiante_id,
            "grupo_id": grupo_id,
            "gestion_id": gestion_id,
            "semestre": semestre,
        },
    }


@router.get("/mis-inscripciones")
def get_mis_inscripciones(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    gestion_id: Optional[int] = Query(None, description="Filtrar por gestión"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Mis inscripciones del estudiante actual con paginación"""

    def query_mis_inscripciones(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Inscripcion).filter(
            Inscripcion.estudiante_id == current_user.id
        )

        if gestion_id:
            query = query.filter(Inscripcion.gestion_id == gestion_id)

        inscripciones = query.offset(offset).limit(limit).all()

        result = []
        for i in inscripciones:
            grupo = db.query(Grupo).filter(Grupo.id == i.grupo_id).first()
            gestion = db.query(Gestion).filter(Gestion.id == i.gestion_id).first()

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
                    "id": i.id,
                    "semestre": i.semestre,
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
                            "creditos": materia.creditos,
                        }
                        if materia
                        else None
                    ),
                    "docente": (
                        f"{docente.nombre} {docente.apellido}" if docente else None
                    ),
                    "gestion": (
                        {
                            "id": gestion.id,
                            "descripcion": f"SEM {gestion.semestre}/{gestion.año}",
                            "semestre": gestion.semestre,
                            "año": gestion.año,
                        }
                        if gestion
                        else None
                    ),
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="mis_inscripciones",
        query_function=query_mis_inscripciones,
        query_params={"gestion_id": gestion_id},
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {"gestion_id": gestion_id},
        "estudiante": {
            "id": current_user.id,
            "registro": current_user.registro,
            "nombre_completo": f"{current_user.nombre} {current_user.apellido}",
        },
    }


@router.get("/{inscripcion_id}")
def get_inscripcion(
    inscripcion_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver inscripción específica con detalles completos"""
    inscripcion = db.query(Inscripcion).filter(Inscripcion.id == inscripcion_id).first()
    if not inscripcion:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada")

    # Obtener información relacionada
    estudiante = (
        db.query(Estudiante).filter(Estudiante.id == inscripcion.estudiante_id).first()
    )
    grupo = db.query(Grupo).filter(Grupo.id == inscripcion.grupo_id).first()
    gestion = db.query(Gestion).filter(Gestion.id == inscripcion.gestion_id).first()

    materia = None
    docente = None
    if grupo:
        materia = db.query(Materia).filter(Materia.id == grupo.materia_id).first()
        docente = db.query(Docente).filter(Docente.id == grupo.docente_id).first()

    return {
        "id": inscripcion.id,
        "semestre": inscripcion.semestre,
        "estudiante": (
            {
                "id": estudiante.id,
                "registro": estudiante.registro,
                "nombre": estudiante.nombre,
                "apellido": estudiante.apellido,
                "ci": estudiante.ci,
            }
            if estudiante
            else None
        ),
        "grupo": (
            {
                "id": grupo.id,
                "descripcion": grupo.descripcion,
                "horario_id": grupo.horario_id,
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
                "es_electiva": materia.es_electiva,
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
        "gestion": (
            {
                "id": gestion.id,
                "semestre": gestion.semestre,
                "año": gestion.año,
                "descripcion": f"SEM {gestion.semestre}/{gestion.año}",
            }
            if gestion
            else None
        ),
        "created_at": (
            inscripcion.created_at.isoformat() if inscripcion.created_at else None
        ),
        "updated_at": (
            inscripcion.updated_at.isoformat() if inscripcion.updated_at else None
        ),
    }


@router.post("/inscribirse")
def inscribirse_a_grupo(
    inscripcion_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Inscribirse a un grupo (el estudiante actual)"""
    try:
        # Validar campos requeridos
        required_fields = ["grupo_id", "gestion_id", "semestre"]
        missing_fields = [
            field for field in required_fields if field not in inscripcion_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que el grupo existe
        grupo = db.query(Grupo).filter(Grupo.id == inscripcion_data["grupo_id"]).first()
        if not grupo:
            raise HTTPException(status_code=400, detail="Grupo no encontrado")

        # Verificar que la gestión existe
        gestion = (
            db.query(Gestion)
            .filter(Gestion.id == inscripcion_data["gestion_id"])
            .first()
        )
        if not gestion:
            raise HTTPException(status_code=400, detail="Gestión no encontrada")

        # Verificar que el estudiante no esté ya inscrito en el mismo grupo
        existing = (
            db.query(Inscripcion)
            .filter(
                Inscripcion.estudiante_id == current_user.id,
                Inscripcion.grupo_id == inscripcion_data["grupo_id"],
                Inscripcion.gestion_id == inscripcion_data["gestion_id"],
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Ya estás inscrito en este grupo para esta gestión",
            )

        # Agregar el ID del estudiante actual
        inscripcion_data["estudiante_id"] = current_user.id

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_inscripcion",
            data=inscripcion_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Inscripción en cola de procesamiento",
            "status": "pending",
            "grupo_id": inscripcion_data["grupo_id"],
            "check_status": f"/queue/tasks/{task_id}",
            "estimated_processing": "1-3 segundos",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
def create_inscripcion(
    inscripcion_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear inscripción (para administradores)"""
    try:
        # Validar campos requeridos
        required_fields = ["estudiante_id", "grupo_id", "gestion_id", "semestre"]
        missing_fields = [
            field for field in required_fields if field not in inscripcion_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar referencias
        if (
            not db.query(Estudiante)
            .filter(Estudiante.id == inscripcion_data["estudiante_id"])
            .first()
        ):
            raise HTTPException(status_code=400, detail="Estudiante no encontrado")

        if not db.query(Grupo).filter(Grupo.id == inscripcion_data["grupo_id"]).first():
            raise HTTPException(status_code=400, detail="Grupo no encontrado")

        if (
            not db.query(Gestion)
            .filter(Gestion.id == inscripcion_data["gestion_id"])
            .first()
        ):
            raise HTTPException(status_code=400, detail="Gestión no encontrada")

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_inscripcion",
            data=inscripcion_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Inscripción en cola de procesamiento",
            "status": "pending",
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{inscripcion_id}")
def update_inscripcion(
    inscripcion_id: int,
    inscripcion_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Actualizar inscripción"""
    try:
        # Verificar que existe
        existing_inscripcion = (
            db.query(Inscripcion).filter(Inscripcion.id == inscripcion_id).first()
        )
        if not existing_inscripcion:
            raise HTTPException(status_code=404, detail="Inscripción no encontrada")

        # Agregar ID a los datos
        inscripcion_data["id"] = inscripcion_id

        task_id = sync_thread_queue_manager.add_task(
            task_type="update_inscripcion",
            data=inscripcion_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Actualización en cola de procesamiento",
            "status": "pending",
            "inscripcion_id": inscripcion_id,
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{inscripcion_id}")
def delete_inscripcion(
    inscripcion_id: int,
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Eliminar inscripción"""
    try:
        # Verificar que existe
        inscripcion = (
            db.query(Inscripcion).filter(Inscripcion.id == inscripcion_id).first()
        )
        if not inscripcion:
            raise HTTPException(status_code=404, detail="Inscripción no encontrada")

        # Verificar permisos (el estudiante solo puede eliminar sus propias inscripciones)
        # En un sistema real, aquí verificarías roles/permisos
        if inscripcion.estudiante_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="No tienes permisos para eliminar esta inscripción",
            )

        task_id = sync_thread_queue_manager.add_task(
            task_type="delete_inscripcion",
            data={"id": inscripcion_id},
            priority=priority,
            max_retries=2,
        )

        return {
            "task_id": task_id,
            "message": "Eliminación en cola de procesamiento",
            "status": "pending",
            "inscripcion_id": inscripcion_id,
            "check_status": f"/queue/tasks/{task_id}",
            "warning": "Esta operación no se puede deshacer",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/estadisticas/resumen")
def get_estadisticas_inscripciones(
    gestion_id: Optional[int] = Query(None, description="Filtrar por gestión"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener estadísticas de inscripciones"""
    query = db.query(Inscripcion)

    if gestion_id:
        query = query.filter(Inscripcion.gestion_id == gestion_id)

    total_inscripciones = query.count()

    # Inscripciones por semestre
    semestres = {}
    for semestre in [1, 2, 3, 4]:
        count = query.filter(Inscripcion.semestre == semestre).count()
        semestres[f"semestre_{semestre}"] = count

    # Top 5 grupos con más inscripciones
    from sqlalchemy import func

    top_grupos = (
        db.query(Grupo.descripcion, func.count(Inscripcion.id).label("count"))
        .join(Inscripcion, Grupo.id == Inscripcion.grupo_id)
        .group_by(Grupo.id, Grupo.descripcion)
        .order_by(func.count(Inscripcion.id).desc())
        .limit(5)
        .all()
    )

    return {
        "total_inscripciones": total_inscripciones,
        "por_semestre": semestres,
        "top_grupos": [
            {"grupo": grupo, "inscripciones": count} for grupo, count in top_grupos
        ],
        "gestion_filtrada": gestion_id,
    }
