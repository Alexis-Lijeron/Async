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
    estudiante_registro: Optional[str] = Query(
        None, description="Filtrar por registro de estudiante"
    ),
    grupo_codigo: Optional[str] = Query(
        None, description="Filtrar por código de grupo"
    ),
    gestion_codigo: Optional[str] = Query(
        None, description="Filtrar por código de gestión"
    ),
    semestre: Optional[int] = Query(None, description="Filtrar por semestre"),
    search: Optional[str] = Query(None, description="Buscar por código de inscripción"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de inscripciones con paginación inteligente (SÍNCRONO)"""

    def query_inscripciones(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Inscripcion)

        if estudiante_registro:
            estudiante = (
                db.query(Estudiante)
                .filter(Estudiante.registro == estudiante_registro)
                .first()
            )
            if estudiante:
                query = query.filter(Inscripcion.estudiante_id == estudiante.id)

        if grupo_codigo:
            grupo = db.query(Grupo).filter(Grupo.codigo_grupo == grupo_codigo).first()
            if grupo:
                query = query.filter(Inscripcion.grupo_id == grupo.id)

        if gestion_codigo:
            gestion = (
                db.query(Gestion)
                .filter(Gestion.codigo_gestion == gestion_codigo)
                .first()
            )
            if gestion:
                query = query.filter(Inscripcion.gestion_id == gestion.id)

        if semestre:
            query = query.filter(Inscripcion.semestre == semestre)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(Inscripcion.codigo_inscripcion.ilike(search_pattern))

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
                    "codigo_inscripcion": i.codigo_inscripcion,
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
                            "codigo_grupo": grupo.codigo_grupo,
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
                            "codigo_docente": docente.codigo_docente,
                            "nombre_completo": f"{docente.nombre} {docente.apellido}",
                        }
                        if docente
                        else None
                    ),
                    "gestion": (
                        {
                            "id": gestion.id,
                            "codigo_gestion": gestion.codigo_gestion,
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
            "estudiante_registro": estudiante_registro,
            "grupo_codigo": grupo_codigo,
            "gestion_codigo": gestion_codigo,
            "semestre": semestre,
            "search": search,
        },
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {
            "estudiante_registro": estudiante_registro,
            "grupo_codigo": grupo_codigo,
            "gestion_codigo": gestion_codigo,
            "semestre": semestre,
            "search": search,
        },
    }


@router.get("/mis-inscripciones")
def get_mis_inscripciones(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    gestion_codigo: Optional[str] = Query(
        None, description="Filtrar por código de gestión"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Mis inscripciones del estudiante actual con paginación"""

    def query_mis_inscripciones(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Inscripcion).filter(
            Inscripcion.estudiante_id == current_user.id
        )

        if gestion_codigo:
            gestion = (
                db.query(Gestion)
                .filter(Gestion.codigo_gestion == gestion_codigo)
                .first()
            )
            if gestion:
                query = query.filter(Inscripcion.gestion_id == gestion.id)

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
                    "codigo_inscripcion": i.codigo_inscripcion,
                    "semestre": i.semestre,
                    "grupo": (
                        {
                            "id": grupo.id,
                            "codigo_grupo": grupo.codigo_grupo,
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
                            "codigo_docente": docente.codigo_docente,
                            "nombre_completo": f"{docente.nombre} {docente.apellido}",
                        }
                        if docente
                        else None
                    ),
                    "gestion": (
                        {
                            "id": gestion.id,
                            "codigo_gestion": gestion.codigo_gestion,
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
        query_params={"gestion_codigo": gestion_codigo},
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {"gestion_codigo": gestion_codigo},
        "estudiante": {
            "id": current_user.id,
            "registro": current_user.registro,
            "nombre_completo": f"{current_user.nombre} {current_user.apellido}",
        },
    }


@router.get("/{codigo_inscripcion}")
def get_inscripcion(
    codigo_inscripcion: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver inscripción específica con detalles completos"""
    inscripcion = (
        db.query(Inscripcion)
        .filter(Inscripcion.codigo_inscripcion == codigo_inscripcion)
        .first()
    )
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
        "codigo_inscripcion": inscripcion.codigo_inscripcion,
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
                "codigo_grupo": grupo.codigo_grupo,
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
                "codigo_docente": docente.codigo_docente,
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
                "codigo_gestion": gestion.codigo_gestion,
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
        required_fields = [
            "codigo_inscripcion",
            "grupo_codigo",
            "gestion_codigo",
            "semestre",
        ]
        missing_fields = [
            field for field in required_fields if field not in inscripcion_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que no exista el código de inscripción
        existing_codigo = (
            db.query(Inscripcion)
            .filter(
                Inscripcion.codigo_inscripcion == inscripcion_data["codigo_inscripcion"]
            )
            .first()
        )
        if existing_codigo:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe una inscripción con el código '{inscripcion_data['codigo_inscripcion']}'",
            )

        # Verificar que el grupo existe
        grupo = (
            db.query(Grupo)
            .filter(Grupo.codigo_grupo == inscripcion_data["grupo_codigo"])
            .first()
        )
        if not grupo:
            raise HTTPException(
                status_code=400,
                detail=f"No existe grupo con código '{inscripcion_data['grupo_codigo']}'",
            )

        # Verificar que la gestión existe
        gestion = (
            db.query(Gestion)
            .filter(Gestion.codigo_gestion == inscripcion_data["gestion_codigo"])
            .first()
        )
        if not gestion:
            raise HTTPException(
                status_code=400,
                detail=f"No existe gestión con código '{inscripcion_data['gestion_codigo']}'",
            )

        # Verificar que el estudiante no esté ya inscrito en el mismo grupo
        existing = (
            db.query(Inscripcion)
            .filter(
                Inscripcion.estudiante_id == current_user.id,
                Inscripcion.grupo_id == grupo.id,
                Inscripcion.gestion_id == gestion.id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Ya estás inscrito en este grupo para esta gestión",
            )

        # Agregar el ID del estudiante actual y convertir códigos a IDs
        inscripcion_data["estudiante_id"] = current_user.id
        inscripcion_data["grupo_id"] = grupo.id
        inscripcion_data["gestion_id"] = gestion.id

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
            "grupo_codigo": inscripcion_data["grupo_codigo"],
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
        required_fields = [
            "codigo_inscripcion",
            "estudiante_registro",
            "grupo_codigo",
            "gestion_codigo",
            "semestre",
        ]
        missing_fields = [
            field for field in required_fields if field not in inscripcion_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que no exista el código de inscripción
        existing_codigo = (
            db.query(Inscripcion)
            .filter(
                Inscripcion.codigo_inscripcion == inscripcion_data["codigo_inscripcion"]
            )
            .first()
        )
        if existing_codigo:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe una inscripción con el código '{inscripcion_data['codigo_inscripcion']}'",
            )

        # Verificar referencias y convertir códigos a IDs
        estudiante = (
            db.query(Estudiante)
            .filter(Estudiante.registro == inscripcion_data["estudiante_registro"])
            .first()
        )
        if not estudiante:
            raise HTTPException(
                status_code=400,
                detail=f"No existe estudiante con registro '{inscripcion_data['estudiante_registro']}'",
            )

        grupo = (
            db.query(Grupo)
            .filter(Grupo.codigo_grupo == inscripcion_data["grupo_codigo"])
            .first()
        )
        if not grupo:
            raise HTTPException(
                status_code=400,
                detail=f"No existe grupo con código '{inscripcion_data['grupo_codigo']}'",
            )

        gestion = (
            db.query(Gestion)
            .filter(Gestion.codigo_gestion == inscripcion_data["gestion_codigo"])
            .first()
        )
        if not gestion:
            raise HTTPException(
                status_code=400,
                detail=f"No existe gestión con código '{inscripcion_data['gestion_codigo']}'",
            )

        # Convertir códigos a IDs
        inscripcion_data["estudiante_id"] = estudiante.id
        inscripcion_data["grupo_id"] = grupo.id
        inscripcion_data["gestion_id"] = gestion.id

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


@router.put("/{codigo_inscripcion}")
def update_inscripcion(
    codigo_inscripcion: str,
    inscripcion_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Actualizar inscripción"""
    try:
        # Verificar que existe
        existing_inscripcion = (
            db.query(Inscripcion)
            .filter(Inscripcion.codigo_inscripcion == codigo_inscripcion)
            .first()
        )
        if not existing_inscripcion:
            raise HTTPException(status_code=404, detail="Inscripción no encontrada")

        # Convertir códigos a IDs si se proporcionan
        if "estudiante_registro" in inscripcion_data:
            estudiante = (
                db.query(Estudiante)
                .filter(Estudiante.registro == inscripcion_data["estudiante_registro"])
                .first()
            )
            if not estudiante:
                raise HTTPException(
                    status_code=400,
                    detail=f"No existe estudiante con registro '{inscripcion_data['estudiante_registro']}'",
                )
            inscripcion_data["estudiante_id"] = estudiante.id

        if "grupo_codigo" in inscripcion_data:
            grupo = (
                db.query(Grupo)
                .filter(Grupo.codigo_grupo == inscripcion_data["grupo_codigo"])
                .first()
            )
            if not grupo:
                raise HTTPException(
                    status_code=400,
                    detail=f"No existe grupo con código '{inscripcion_data['grupo_codigo']}'",
                )
            inscripcion_data["grupo_id"] = grupo.id

        if "gestion_codigo" in inscripcion_data:
            gestion = (
                db.query(Gestion)
                .filter(Gestion.codigo_gestion == inscripcion_data["gestion_codigo"])
                .first()
            )
            if not gestion:
                raise HTTPException(
                    status_code=400,
                    detail=f"No existe gestión con código '{inscripcion_data['gestion_codigo']}'",
                )
            inscripcion_data["gestion_id"] = gestion.id

        # Agregar código original a los datos
        inscripcion_data["codigo_inscripcion_original"] = codigo_inscripcion

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
            "codigo_inscripcion": codigo_inscripcion,
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{codigo_inscripcion}")
def delete_inscripcion(
    codigo_inscripcion: str,
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Eliminar inscripción"""
    try:
        # Verificar que existe
        inscripcion = (
            db.query(Inscripcion)
            .filter(Inscripcion.codigo_inscripcion == codigo_inscripcion)
            .first()
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
            data={"codigo_inscripcion": codigo_inscripcion},
            priority=priority,
            max_retries=2,
        )

        return {
            "task_id": task_id,
            "message": "Eliminación en cola de procesamiento",
            "status": "pending",
            "codigo_inscripcion": codigo_inscripcion,
            "check_status": f"/queue/tasks/{task_id}",
            "warning": "Esta operación no se puede deshacer",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/estadisticas/resumen")
def get_estadisticas_inscripciones(
    gestion_codigo: Optional[str] = Query(
        None, description="Filtrar por código de gestión"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener estadísticas de inscripciones"""
    query = db.query(Inscripcion)

    if gestion_codigo:
        gestion = (
            db.query(Gestion).filter(Gestion.codigo_gestion == gestion_codigo).first()
        )
        if gestion:
            query = query.filter(Inscripcion.gestion_id == gestion.id)

    total_inscripciones = query.count()

    # Inscripciones por semestre
    semestres = {}
    for semestre in [1, 2, 3, 4]:
        count = query.filter(Inscripcion.semestre == semestre).count()
        semestres[f"semestre_{semestre}"] = count

    # Top 5 grupos con más inscripciones
    from sqlalchemy import func

    top_grupos = (
        db.query(
            Grupo.codigo_grupo,
            Grupo.descripcion,
            func.count(Inscripcion.id).label("count"),
        )
        .join(Inscripcion, Grupo.id == Inscripcion.grupo_id)
        .group_by(Grupo.id, Grupo.codigo_grupo, Grupo.descripcion)
        .order_by(func.count(Inscripcion.id).desc())
        .limit(5)
        .all()
    )

    return {
        "total_inscripciones": total_inscripciones,
        "por_semestre": semestres,
        "top_grupos": [
            {"codigo_grupo": codigo, "descripcion": descripcion, "inscripciones": count}
            for codigo, descripcion, count in top_grupos
        ],
        "gestion_filtrada": gestion_codigo,
    }
