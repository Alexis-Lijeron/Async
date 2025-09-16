from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.docente import Docente
from app.models.grupo import Grupo
from app.models.materia import Materia
from app.models.gestion import Gestion
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_docentes(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    search: Optional[str] = Query(
        None, description="Buscar por nombre, apellido o código"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de docentes con paginación inteligente (SÍNCRONO)"""

    def query_docentes(db: Session, offset: int, limit: int, **kwargs):
        """Función de consulta para paginación"""
        query = db.query(Docente)

        # Aplicar filtros
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Docente.nombre.ilike(search_pattern))
                | (Docente.apellido.ilike(search_pattern))
                | (Docente.codigo_docente.ilike(search_pattern))
            )

        docentes = query.offset(offset).limit(limit).all()

        # Obtener información adicional
        docentes_data = []
        for d in docentes:
            # Contar grupos asignados
            grupos_count = db.query(Grupo).filter(Grupo.docente_id == d.id).count()

            # Obtener grupos actuales
            grupos_actuales = (
                db.query(Grupo)
                .filter(Grupo.docente_id == d.id)
                .limit(3)  # Solo mostrar los primeros 3
                .all()
            )

            grupos_info = []
            for g in grupos_actuales:
                materia = db.query(Materia).filter(Materia.id == g.materia_id).first()
                gestion = db.query(Gestion).filter(Gestion.id == g.gestion_id).first()
                grupos_info.append(
                    {
                        "id": g.id,
                        "codigo_grupo": g.codigo_grupo,
                        "descripcion": g.descripcion,
                        "materia_sigla": materia.sigla if materia else None,
                        "gestion": (
                            f"SEM {gestion.semestre}/{gestion.año}" if gestion else None
                        ),
                    }
                )

            docentes_data.append(
                {
                    "id": d.id,
                    "codigo_docente": d.codigo_docente,
                    "nombre": d.nombre,
                    "apellido": d.apellido,
                    "nombre_completo": f"{d.nombre} {d.apellido}",
                    "grupos_count": grupos_count,
                    "grupos_actuales": grupos_info,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                }
            )

        return docentes_data

    # Generar session_id si no se proporciona
    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    # Usar paginación inteligente
    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="docentes_list",
        query_function=query_docentes,
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


@router.get("/search")
def search_docentes(
    name: str = Query(..., description="Nombre, apellido o código a buscar"),
    exact_match: bool = Query(False, description="Búsqueda exacta"),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Buscar docentes por nombre o código (endpoint simplificado)"""
    if exact_match:
        docentes = (
            db.query(Docente)
            .filter(
                (Docente.nombre.ilike(name))
                | (Docente.apellido.ilike(name))
                | (Docente.codigo_docente.ilike(name))
            )
            .limit(page_size)
            .all()
        )
    else:
        search_pattern = f"%{name}%"
        docentes = (
            db.query(Docente)
            .filter(
                (Docente.nombre.ilike(search_pattern))
                | (Docente.apellido.ilike(search_pattern))
                | (Docente.codigo_docente.ilike(search_pattern))
            )
            .limit(page_size)
            .all()
        )

    return [
        {
            "id": d.id,
            "codigo_docente": d.codigo_docente,
            "nombre": d.nombre,
            "apellido": d.apellido,
            "nombre_completo": f"{d.nombre} {d.apellido}",
        }
        for d in docentes
    ]


@router.get("/{codigo_docente}")
def get_docente(
    codigo_docente: str,
    include_grupos: bool = Query(False, description="Incluir grupos del docente"),
    include_statistics: bool = Query(True, description="Incluir estadísticas"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener docente específico con detalles completos"""
    docente = db.query(Docente).filter(Docente.codigo_docente == codigo_docente).first()
    if not docente:
        raise HTTPException(status_code=404, detail="Docente no encontrado")

    # Datos básicos
    docente_data = {
        "id": docente.id,
        "codigo_docente": docente.codigo_docente,
        "nombre": docente.nombre,
        "apellido": docente.apellido,
        "nombre_completo": f"{docente.nombre} {docente.apellido}",
        "created_at": docente.created_at.isoformat() if docente.created_at else None,
        "updated_at": docente.updated_at.isoformat() if docente.updated_at else None,
    }

    # Incluir estadísticas
    if include_statistics:
        grupos_count = db.query(Grupo).filter(Grupo.docente_id == docente.id).count()

        # Materias únicas que imparte
        materias_query = (
            db.query(Materia)
            .join(Grupo, Materia.id == Grupo.materia_id)
            .filter(Grupo.docente_id == docente.id)
            .distinct()
        )
        materias_count = materias_query.count()

        # Gestiones en las que ha trabajado
        gestiones_query = (
            db.query(Gestion)
            .join(Grupo, Gestion.id == Grupo.gestion_id)
            .filter(Grupo.docente_id == docente.id)
            .distinct()
        )
        gestiones_count = gestiones_query.count()

        docente_data["statistics"] = {
            "total_grupos": grupos_count,
            "materias_impartidas": materias_count,
            "gestiones_participadas": gestiones_count,
        }

    # Incluir grupos si se solicita
    if include_grupos:
        grupos = (
            db.query(Grupo)
            .filter(Grupo.docente_id == docente.id)
            .limit(20)  # Límite para evitar sobrecarga
            .all()
        )

        grupos_info = []
        for g in grupos:
            materia = db.query(Materia).filter(Materia.id == g.materia_id).first()
            gestion = db.query(Gestion).filter(Gestion.id == g.gestion_id).first()

            grupos_info.append(
                {
                    "id": g.id,
                    "codigo_grupo": g.codigo_grupo,
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
                }
            )

        docente_data["grupos"] = grupos_info

    return docente_data


@router.post("/")
def create_docente(
    docente_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear docente (procesamiento síncrono)"""
    try:
        # Validar campos requeridos
        required_fields = ["codigo_docente", "nombre", "apellido"]
        missing_fields = [
            field for field in required_fields if field not in docente_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Validaciones adicionales
        if len(docente_data["nombre"].strip()) < 2:
            raise HTTPException(
                status_code=400, detail="El nombre debe tener al menos 2 caracteres"
            )

        if len(docente_data["apellido"].strip()) < 2:
            raise HTTPException(
                status_code=400, detail="El apellido debe tener al menos 2 caracteres"
            )

        # Verificar si ya existe un docente con el mismo código
        existing = (
            db.query(Docente)
            .filter(Docente.codigo_docente == docente_data["codigo_docente"])
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un docente con el código '{docente_data['codigo_docente']}'",
            )

        # Configurar rollback
        rollback_data = {
            "operation": "create",
            "table": "docentes",
            "created_by": current_user.id,
        }

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_docente",
            data=docente_data,
            priority=priority,
            max_retries=3,
            rollback_data=rollback_data,
        )

        return {
            "task_id": task_id,
            "message": "Docente en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "check_status": f"/queue/tasks/{task_id}",
            "estimated_processing": "1-3 segundos",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{codigo_docente}")
def update_docente(
    codigo_docente: str,
    docente_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Actualizar docente (procesamiento síncrono con rollback)"""
    try:
        # Verificar que existe
        existing_docente = (
            db.query(Docente).filter(Docente.codigo_docente == codigo_docente).first()
        )
        if not existing_docente:
            raise HTTPException(status_code=404, detail="Docente no encontrado")

        # Validaciones si se están cambiando los campos
        if "nombre" in docente_data and len(docente_data["nombre"].strip()) < 2:
            raise HTTPException(
                status_code=400, detail="El nombre debe tener al menos 2 caracteres"
            )

        if "apellido" in docente_data and len(docente_data["apellido"].strip()) < 2:
            raise HTTPException(
                status_code=400, detail="El apellido debe tener al menos 2 caracteres"
            )

        # Verificar código único si se está cambiando
        if (
            "codigo_docente" in docente_data
            and docente_data["codigo_docente"] != existing_docente.codigo_docente
        ):
            duplicate = (
                db.query(Docente)
                .filter(
                    Docente.codigo_docente == docente_data["codigo_docente"],
                    Docente.id != existing_docente.id,
                )
                .first()
            )
            if duplicate:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe un docente con el código '{docente_data['codigo_docente']}'",
                )

        # Agregar código original a los datos
        docente_data["codigo_docente_original"] = codigo_docente

        # Configurar rollback con estado original
        rollback_data = {
            "operation": "update",
            "table": "docentes",
            "codigo_original": codigo_docente,
            "original_data": {
                "codigo_docente": existing_docente.codigo_docente,
                "nombre": existing_docente.nombre,
                "apellido": existing_docente.apellido,
            },
            "updated_by": current_user.id,
        }

        task_id = sync_thread_queue_manager.add_task(
            task_type="update_docente",
            data=docente_data,
            priority=priority,
            max_retries=3,
            rollback_data=rollback_data,
        )

        return {
            "task_id": task_id,
            "message": "Actualización en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "codigo_docente": codigo_docente,
            "check_status": f"/queue/tasks/{task_id}",
            "rollback_available": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{codigo_docente}")
def delete_docente(
    codigo_docente: str,
    force: bool = Query(False, description="Forzar eliminación aunque tenga grupos"),
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Eliminar docente (procesamiento síncrono)"""
    try:
        # Verificar que existe
        docente = (
            db.query(Docente).filter(Docente.codigo_docente == codigo_docente).first()
        )
        if not docente:
            raise HTTPException(status_code=404, detail="Docente no encontrado")

        # Verificar si tiene grupos asignados
        grupos_count = db.query(Grupo).filter(Grupo.docente_id == docente.id).count()
        if grupos_count > 0 and not force:
            # Obtener algunos grupos para mostrar información
            grupos_sample = (
                db.query(Grupo).filter(Grupo.docente_id == docente.id).limit(3).all()
            )
            grupos_info = []
            for g in grupos_sample:
                materia = db.query(Materia).filter(Materia.id == g.materia_id).first()
                grupos_info.append(
                    f"{materia.sigla if materia else 'N/A'} - {g.descripcion}"
                )

            raise HTTPException(
                status_code=400,
                detail=f"No se puede eliminar el docente porque tiene {grupos_count} grupos asignados. "
                f"Grupos: {', '.join(grupos_info[:3])}{'...' if grupos_count > 3 else ''}. "
                f"Use force=true para forzar la eliminación.",
            )

        task_id = sync_thread_queue_manager.add_task(
            task_type="delete_docente",
            data={"codigo_docente": codigo_docente, "force": force},
            priority=priority,
            max_retries=2,
        )

        return {
            "task_id": task_id,
            "message": "Eliminación en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "codigo_docente": codigo_docente,
            "groups_affected": grupos_count if force else 0,
            "check_status": f"/queue/tasks/{task_id}",
            "warning": "Esta operación no se puede deshacer"
            + (
                f" y afectará a {grupos_count} grupos"
                if force and grupos_count > 0
                else ""
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{codigo_docente}/grupos")
def get_docente_grupos(
    codigo_docente: str,
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    gestion_codigo: Optional[str] = Query(None, description="Filtrar por gestión"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener grupos de un docente específico con paginación"""
    # Verificar que el docente existe
    docente = db.query(Docente).filter(Docente.codigo_docente == codigo_docente).first()
    if not docente:
        raise HTTPException(status_code=404, detail="Docente no encontrado")

    def query_grupos_docente(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Grupo).filter(Grupo.docente_id == docente.id)

        if gestion_codigo:
            gestion = (
                db.query(Gestion)
                .filter(Gestion.codigo_gestion == gestion_codigo)
                .first()
            )
            if gestion:
                query = query.filter(Grupo.gestion_id == gestion.id)

        grupos = query.offset(offset).limit(limit).all()

        grupos_info = []
        for g in grupos:
            materia = db.query(Materia).filter(Materia.id == g.materia_id).first()
            gestion = db.query(Gestion).filter(Gestion.id == g.gestion_id).first()

            grupos_info.append(
                {
                    "id": g.id,
                    "codigo_grupo": g.codigo_grupo,
                    "descripcion": g.descripcion,
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
                    "horario_id": g.horario_id,
                }
            )

        return grupos_info

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint=f"docente_{codigo_docente}_grupos",
        query_function=query_grupos_docente,
        query_params={"gestion_codigo": gestion_codigo},
        page_size=page_size,
    )

    return {
        "docente": {
            "id": docente.id,
            "codigo_docente": docente.codigo_docente,
            "nombre": docente.nombre,
            "apellido": docente.apellido,
            "nombre_completo": f"{docente.nombre} {docente.apellido}",
        },
        "grupos": results,
        "pagination": metadata,
        "filters": {"gestion_codigo": gestion_codigo},
    }
