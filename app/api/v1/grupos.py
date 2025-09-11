from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.grupo import Grupo
from app.models.materia import Materia
from app.models.docente import Docente
from app.models.gestion import Gestion
from app.models.horario import Horario
from app.models.inscripcion import Inscripcion
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_grupos(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    search: Optional[str] = Query(None, description="Buscar por descripción"),
    materia_id: Optional[int] = Query(None, description="Filtrar por materia"),
    docente_id: Optional[int] = Query(None, description="Filtrar por docente"),
    gestion_id: Optional[int] = Query(None, description="Filtrar por gestión"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de grupos con paginación inteligente (SÍNCRONO)"""

    def query_grupos(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Grupo)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(Grupo.descripcion.ilike(search_pattern))

        if materia_id:
            query = query.filter(Grupo.materia_id == materia_id)

        if docente_id:
            query = query.filter(Grupo.docente_id == docente_id)

        if gestion_id:
            query = query.filter(Grupo.gestion_id == gestion_id)

        grupos = query.offset(offset).limit(limit).all()

        grupos_data = []
        for g in grupos:
            materia = db.query(Materia).filter(Materia.id == g.materia_id).first()
            docente = db.query(Docente).filter(Docente.id == g.docente_id).first()
            gestion = db.query(Gestion).filter(Gestion.id == g.gestion_id).first()
            horario = db.query(Horario).filter(Horario.id == g.horario_id).first()

            inscripciones_count = (
                db.query(Inscripcion).filter(Inscripcion.grupo_id == g.id).count()
            )

            grupos_data.append(
                {
                    "id": g.id,
                    "descripcion": g.descripcion,
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
                    "gestion": (
                        {
                            "id": gestion.id,
                            "descripcion": f"SEM {gestion.semestre}/{gestion.año}",
                        }
                        if gestion
                        else None
                    ),
                    "horario": (
                        {
                            "id": horario.id,
                            "dia": horario.dia,
                            "hora_inicio": str(horario.hora_inicio),
                            "hora_final": str(horario.hora_final),
                        }
                        if horario
                        else None
                    ),
                    "estudiantes_inscritos": inscripciones_count,
                    "created_at": g.created_at.isoformat() if g.created_at else None,
                }
            )

        return grupos_data

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="grupos_list",
        query_function=query_grupos,
        query_params={
            "search": search,
            "materia_id": materia_id,
            "docente_id": docente_id,
            "gestion_id": gestion_id,
        },
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {
            "search": search,
            "materia_id": materia_id,
            "docente_id": docente_id,
            "gestion_id": gestion_id,
        },
    }


@router.get("/{grupo_id}")
def get_grupo(
    grupo_id: int,
    include_inscripciones: bool = Query(False, description="Incluir inscripciones"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver grupo específico con detalles"""
    grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")

    # Obtener información relacionada
    materia = db.query(Materia).filter(Materia.id == grupo.materia_id).first()
    docente = db.query(Docente).filter(Docente.id == grupo.docente_id).first()
    gestion = db.query(Gestion).filter(Gestion.id == grupo.gestion_id).first()
    horario = db.query(Horario).filter(Horario.id == grupo.horario_id).first()

    grupo_data = {
        "id": grupo.id,
        "descripcion": grupo.descripcion,
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
        "horario": (
            {
                "id": horario.id,
                "dia": horario.dia,
                "hora_inicio": str(horario.hora_inicio),
                "hora_final": str(horario.hora_final),
            }
            if horario
            else None
        ),
        "created_at": grupo.created_at.isoformat() if grupo.created_at else None,
    }

    # Estadísticas
    inscripciones_count = (
        db.query(Inscripcion).filter(Inscripcion.grupo_id == grupo.id).count()
    )
    grupo_data["statistics"] = {
        "total_inscripciones": inscripciones_count,
    }

    if include_inscripciones:
        from app.models.estudiante import Estudiante

        inscripciones = (
            db.query(Inscripcion)
            .filter(Inscripcion.grupo_id == grupo.id)
            .limit(50)
            .all()
        )
        estudiantes_info = []
        for i in inscripciones:
            estudiante = (
                db.query(Estudiante).filter(Estudiante.id == i.estudiante_id).first()
            )
            if estudiante:
                estudiantes_info.append(
                    {
                        "inscripcion_id": i.id,
                        "estudiante": {
                            "id": estudiante.id,
                            "registro": estudiante.registro,
                            "nombre": estudiante.nombre,
                            "apellido": estudiante.apellido,
                        },
                    }
                )
        grupo_data["inscripciones"] = estudiantes_info

    return grupo_data


@router.post("/")
def create_grupo(
    grupo_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear grupo (procesamiento síncrono)"""
    try:
        required_fields = [
            "descripcion",
            "docente_id",
            "materia_id",
            "gestion_id",
            "horario_id",
        ]
        missing_fields = [field for field in required_fields if field not in grupo_data]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar referencias
        if not db.query(Docente).filter(Docente.id == grupo_data["docente_id"]).first():
            raise HTTPException(status_code=400, detail="Docente no existe")

        if not db.query(Materia).filter(Materia.id == grupo_data["materia_id"]).first():
            raise HTTPException(status_code=400, detail="Materia no existe")

        if not db.query(Gestion).filter(Gestion.id == grupo_data["gestion_id"]).first():
            raise HTTPException(status_code=400, detail="Gestión no existe")

        if not db.query(Horario).filter(Horario.id == grupo_data["horario_id"]).first():
            raise HTTPException(status_code=400, detail="Horario no existe")

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_grupo",
            data=grupo_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Grupo en cola de procesamiento",
            "status": "pending",
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{grupo_id}")
def update_grupo(
    grupo_id: int,
    grupo_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Actualizar grupo (procesamiento síncrono)"""
    try:
        # Verificar que existe
        existing_grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
        if not existing_grupo:
            raise HTTPException(status_code=404, detail="Grupo no encontrado")

        # Agregar ID a los datos
        grupo_data["id"] = grupo_id

        task_id = sync_thread_queue_manager.add_task(
            task_type="update_grupo",
            data=grupo_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Actualización en cola de procesamiento",
            "status": "pending",
            "grupo_id": grupo_id,
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{grupo_id}")
def delete_grupo(
    grupo_id: int,
    force: bool = Query(
        False, description="Forzar eliminación aunque tenga inscripciones"
    ),
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Eliminar grupo (procesamiento síncrono)"""
    try:
        # Verificar que existe
        grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
        if not grupo:
            raise HTTPException(status_code=404, detail="Grupo no encontrado")

        # Verificar si tiene inscripciones
        inscripciones_count = (
            db.query(Inscripcion).filter(Inscripcion.grupo_id == grupo_id).count()
        )
        if inscripciones_count > 0 and not force:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede eliminar el grupo porque tiene {inscripciones_count} inscripciones. Use force=true para forzar la eliminación.",
            )

        task_id = sync_thread_queue_manager.add_task(
            task_type="delete_grupo",
            data={"id": grupo_id, "force": force},
            priority=priority,
            max_retries=2,
        )

        return {
            "task_id": task_id,
            "message": "Eliminación en cola de procesamiento",
            "status": "pending",
            "grupo_id": grupo_id,
            "inscripciones_affected": inscripciones_count if force else 0,
            "check_status": f"/queue/tasks/{task_id}",
            "warning": "Esta operación no se puede deshacer"
            + (
                f" y afectará a {inscripciones_count} inscripciones"
                if force and inscripciones_count > 0
                else ""
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/materia/{materia_id}")
def get_grupos_by_materia(
    materia_id: int,
    session_id: Optional[str] = Query(None),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener grupos por materia"""
    # Verificar que la materia existe
    materia = db.query(Materia).filter(Materia.id == materia_id).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")

    def query_grupos_materia(db: Session, offset: int, limit: int, **kwargs):
        grupos = (
            db.query(Grupo)
            .filter(Grupo.materia_id == materia_id)
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for g in grupos:
            docente = db.query(Docente).filter(Docente.id == g.docente_id).first()
            gestion = db.query(Gestion).filter(Gestion.id == g.gestion_id).first()
            result.append(
                {
                    "id": g.id,
                    "descripcion": g.descripcion,
                    "docente": (
                        f"{docente.nombre} {docente.apellido}" if docente else None
                    ),
                    "gestion": (
                        f"SEM {gestion.semestre}/{gestion.año}" if gestion else None
                    ),
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint=f"grupos_materia_{materia_id}",
        query_function=query_grupos_materia,
        query_params={},
        page_size=page_size,
    )

    return {
        "materia": {
            "id": materia.id,
            "sigla": materia.sigla,
            "nombre": materia.nombre,
        },
        "grupos": results,
        "pagination": metadata,
    }
