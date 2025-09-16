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
    search: Optional[str] = Query(None, description="Buscar por código de gestión"),
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
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(Gestion.codigo_gestion.ilike(search_pattern))

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
                    "codigo_gestion": g.codigo_gestion,
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
        query_params={"año": año, "semestre": semestre, "search": search},
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {"año": año, "semestre": semestre, "search": search},
    }


@router.get("/{codigo_gestion}")
def get_gestion(
    codigo_gestion: str,
    include_grupos: bool = Query(False, description="Incluir grupos de la gestión"),
    include_statistics: bool = Query(True, description="Incluir estadísticas"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver gestión específica con detalles"""
    gestion = db.query(Gestion).filter(Gestion.codigo_gestion == codigo_gestion).first()
    if not gestion:
        raise HTTPException(status_code=404, detail="Gestión no encontrada")

    gestion_data = {
        "id": gestion.id,
        "codigo_gestion": gestion.codigo_gestion,
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
                    "codigo_grupo": grupo.codigo_grupo,
                    "descripcion": grupo.descripcion,
                    "materia_sigla": materia.sigla if materia else None,
                    "docente": (
                        f"{docente.nombre} {docente.apellido}" if docente else None
                    ),
                    "docente_codigo": docente.codigo_docente if docente else None,
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
        required_fields = ["codigo_gestion", "semestre", "año"]
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

        # Verificar que no exista el código de gestión
        existing_codigo = (
            db.query(Gestion)
            .filter(Gestion.codigo_gestion == gestion_data["codigo_gestion"])
            .first()
        )
        if existing_codigo:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe una gestión con el código '{gestion_data['codigo_gestion']}'",
            )

        # Verificar que no exista la misma combinación semestre-año
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


@router.put("/{codigo_gestion}")
def update_gestion(
    codigo_gestion: str,
    gestion_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Actualizar gestión"""
    try:
        # Verificar que existe
        existing_gestion = (
            db.query(Gestion).filter(Gestion.codigo_gestion == codigo_gestion).first()
        )
        if not existing_gestion:
            raise HTTPException(status_code=404, detail="Gestión no encontrada")

        # Verificar código único si se está cambiando
        if (
            "codigo_gestion" in gestion_data
            and gestion_data["codigo_gestion"] != existing_gestion.codigo_gestion
        ):
            duplicate = (
                db.query(Gestion)
                .filter(
                    Gestion.codigo_gestion == gestion_data["codigo_gestion"],
                    Gestion.id != existing_gestion.id,
                )
                .first()
            )
            if duplicate:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe una gestión con el código '{gestion_data['codigo_gestion']}'",
                )

        # Verificar combinación semestre-año única si se está cambiando
        new_semestre = gestion_data.get("semestre", existing_gestion.semestre)
        new_año = gestion_data.get("año", existing_gestion.año)

        if new_semestre != existing_gestion.semestre or new_año != existing_gestion.año:
            duplicate_combo = (
                db.query(Gestion)
                .filter(
                    Gestion.semestre == new_semestre,
                    Gestion.año == new_año,
                    Gestion.id != existing_gestion.id,
                )
                .first()
            )
            if duplicate_combo:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe la gestión Semestre {new_semestre} - {new_año}",
                )

        gestion_data["codigo_gestion_original"] = codigo_gestion

        task_id = sync_thread_queue_manager.add_task(
            "update_gestion", gestion_data, priority=priority
        )
        return {
            "task_id": task_id,
            "message": "Actualización en cola",
            "status": "pending",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{codigo_gestion}")
def delete_gestion(
    codigo_gestion: str,
    force: bool = Query(False, description="Forzar eliminación"),
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Eliminar gestión"""
    try:
        # Verificar que existe
        gestion = (
            db.query(Gestion).filter(Gestion.codigo_gestion == codigo_gestion).first()
        )
        if not gestion:
            raise HTTPException(status_code=404, detail="Gestión no encontrada")

        # Verificar si tiene grupos o inscripciones
        grupos_count = db.query(Grupo).filter(Grupo.gestion_id == gestion.id).count()
        inscripciones_count = (
            db.query(Inscripcion).filter(Inscripcion.gestion_id == gestion.id).count()
        )

        if (grupos_count > 0 or inscripciones_count > 0) and not force:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede eliminar la gestión porque tiene {grupos_count} grupos y {inscripciones_count} inscripciones asociadas. Use force=true para forzar la eliminación.",
            )

        task_id = sync_thread_queue_manager.add_task(
            "delete_gestion",
            {"codigo_gestion": codigo_gestion, "force": force},
            priority=priority,
        )
        return {
            "task_id": task_id,
            "message": "Eliminación en cola",
            "status": "pending",
            "grupos_affected": grupos_count if force else 0,
            "inscripciones_affected": inscripciones_count if force else 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{codigo_gestion}/grupos")
def get_gestion_grupos(
    codigo_gestion: str,
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener grupos de una gestión específica con paginación"""
    # Verificar que la gestión existe
    gestion = db.query(Gestion).filter(Gestion.codigo_gestion == codigo_gestion).first()
    if not gestion:
        raise HTTPException(status_code=404, detail="Gestión no encontrada")

    def query_grupos_gestion(db: Session, offset: int, limit: int, **kwargs):
        grupos = (
            db.query(Grupo)
            .filter(Grupo.gestion_id == gestion.id)
            .offset(offset)
            .limit(limit)
            .all()
        )

        from app.models.materia import Materia
        from app.models.docente import Docente

        result = []
        for g in grupos:
            materia = db.query(Materia).filter(Materia.id == g.materia_id).first()
            docente = db.query(Docente).filter(Docente.id == g.docente_id).first()
            result.append(
                {
                    "id": g.id,
                    "codigo_grupo": g.codigo_grupo,
                    "descripcion": g.descripcion,
                    "materia": (
                        {
                            "sigla": materia.sigla,
                            "nombre": materia.nombre,
                        }
                        if materia
                        else None
                    ),
                    "docente": (
                        {
                            "codigo_docente": docente.codigo_docente,
                            "nombre_completo": f"{docente.nombre} {docente.apellido}",
                        }
                        if docente
                        else None
                    ),
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint=f"gestion_{codigo_gestion}_grupos",
        query_function=query_grupos_gestion,
        query_params={},
        page_size=page_size,
    )

    return {
        "gestion": {
            "id": gestion.id,
            "codigo_gestion": gestion.codigo_gestion,
            "semestre": gestion.semestre,
            "año": gestion.año,
            "descripcion": f"Semestre {gestion.semestre} - {gestion.año}",
        },
        "grupos": results,
        "pagination": metadata,
    }


@router.get("/{codigo_gestion}/inscripciones")
def get_gestion_inscripciones(
    codigo_gestion: str,
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener inscripciones de una gestión específica con paginación"""
    # Verificar que la gestión existe
    gestion = db.query(Gestion).filter(Gestion.codigo_gestion == codigo_gestion).first()
    if not gestion:
        raise HTTPException(status_code=404, detail="Gestión no encontrada")

    def query_inscripciones_gestion(db: Session, offset: int, limit: int, **kwargs):
        inscripciones = (
            db.query(Inscripcion)
            .filter(Inscripcion.gestion_id == gestion.id)
            .offset(offset)
            .limit(limit)
            .all()
        )

        from app.models.estudiante import Estudiante
        from app.models.grupo import Grupo

        result = []
        for i in inscripciones:
            estudiante = (
                db.query(Estudiante).filter(Estudiante.id == i.estudiante_id).first()
            )
            grupo = db.query(Grupo).filter(Grupo.id == i.grupo_id).first()

            result.append(
                {
                    "id": i.id,
                    "codigo_inscripcion": i.codigo_inscripcion,
                    "semestre": i.semestre,
                    "estudiante": (
                        {
                            "registro": estudiante.registro,
                            "nombre_completo": f"{estudiante.nombre} {estudiante.apellido}",
                        }
                        if estudiante
                        else None
                    ),
                    "grupo": (
                        {
                            "codigo_grupo": grupo.codigo_grupo,
                            "descripcion": grupo.descripcion,
                        }
                        if grupo
                        else None
                    ),
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint=f"gestion_{codigo_gestion}_inscripciones",
        query_function=query_inscripciones_gestion,
        query_params={},
        page_size=page_size,
    )

    return {
        "gestion": {
            "id": gestion.id,
            "codigo_gestion": gestion.codigo_gestion,
            "semestre": gestion.semestre,
            "año": gestion.año,
            "descripcion": f"Semestre {gestion.semestre} - {gestion.año}",
        },
        "inscripciones": results,
        "pagination": metadata,
    }
