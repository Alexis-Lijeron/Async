from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.materia import Materia
from app.models.nivel import Nivel
from app.models.plan_estudio import PlanEstudio
from app.models.grupo import Grupo
from app.models.prerrequisito import Prerrequisito
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_materias(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    search: Optional[str] = Query(None, description="Buscar por sigla o nombre"),
    nivel_id: Optional[int] = Query(None, description="Filtrar por nivel/semestre"),
    es_electiva: Optional[bool] = Query(None, description="Filtrar por electivas"),
    plan_estudio_id: Optional[int] = Query(
        None, description="Filtrar por plan de estudios"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de materias con paginación inteligente (SÍNCRONO)"""

    def query_materias(db: Session, offset: int, limit: int, **kwargs):
        """Función de consulta para paginación"""
        query = db.query(Materia)

        # Aplicar filtros
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Materia.sigla.ilike(search_pattern))
                | (Materia.nombre.ilike(search_pattern))
            )

        if nivel_id:
            query = query.filter(Materia.nivel_id == nivel_id)

        if es_electiva is not None:
            query = query.filter(Materia.es_electiva == es_electiva)

        if plan_estudio_id:
            query = query.filter(Materia.plan_estudio_id == plan_estudio_id)

        materias = query.offset(offset).limit(limit).all()

        # Obtener información relacionada
        materias_data = []
        for m in materias:
            # Obtener nivel
            nivel = db.query(Nivel).filter(Nivel.id == m.nivel_id).first()

            # Obtener plan de estudios
            plan = (
                db.query(PlanEstudio)
                .filter(PlanEstudio.id == m.plan_estudio_id)
                .first()
            )

            # Contar grupos
            grupos_count = db.query(Grupo).filter(Grupo.materia_id == m.id).count()

            # Obtener prerrequisitos
            prerrequisitos = (
                db.query(Prerrequisito).filter(Prerrequisito.materia_id == m.id).all()
            )

            materias_data.append(
                {
                    "id": m.id,
                    "sigla": m.sigla,
                    "nombre": m.nombre,
                    "creditos": m.creditos,
                    "es_electiva": m.es_electiva,
                    "nivel": (
                        {
                            "id": nivel.id,
                            "nivel": nivel.nivel,
                            "semestre": f"Semestre {nivel.nivel}",
                        }
                        if nivel
                        else None
                    ),
                    "plan_estudio": (
                        {"id": plan.id, "codigo": plan.codigo, "plan": plan.plan}
                        if plan
                        else None
                    ),
                    "grupos_count": grupos_count,
                    "prerrequisitos_count": len(prerrequisitos),
                    "prerrequisitos": [p.sigla_prerrequisito for p in prerrequisitos],
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
            )

        return materias_data

    # Generar session_id si no se proporciona
    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    # Usar paginación inteligente
    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="materias_list",
        query_function=query_materias,
        query_params={
            "search": search,
            "nivel_id": nivel_id,
            "es_electiva": es_electiva,
            "plan_estudio_id": plan_estudio_id,
        },
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {
            "search": search,
            "nivel_id": nivel_id,
            "es_electiva": es_electiva,
            "plan_estudio_id": plan_estudio_id,
        },
        "instructions": {
            "next_page": f"Usa el mismo session_id '{metadata['session_id']}' para obtener más resultados",
            "reset": f"Para reiniciar usa DELETE /queue/pagination/sessions/{metadata['session_id']}",
        },
    }


@router.get("/electivas")
def get_materias_electivas(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener solo materias electivas"""

    def query_electivas(db: Session, offset: int, limit: int, **kwargs):
        materias = (
            db.query(Materia)
            .filter(Materia.es_electiva == True)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": m.id,
                "sigla": m.sigla,
                "nombre": m.nombre,
                "creditos": m.creditos,
            }
            for m in materias
        ]

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="materias_electivas",
        query_function=query_electivas,
        query_params={},
        page_size=page_size,
    )

    return {"data": results, "pagination": metadata}


@router.get("/semestre/{semestre}")
def get_materias_by_semestre(
    semestre: int,
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Materias por semestre específico"""

    def query_materias_semestre(db: Session, offset: int, limit: int, **kwargs):
        # Buscar el nivel correspondiente al semestre
        nivel = db.query(Nivel).filter(Nivel.nivel == semestre).first()
        if not nivel:
            return []

        materias = (
            db.query(Materia)
            .filter(Materia.nivel_id == nivel.id)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": m.id,
                "sigla": m.sigla,
                "nombre": m.nombre,
                "creditos": m.creditos,
                "es_electiva": m.es_electiva,
            }
            for m in materias
        ]

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint=f"materias_semestre_{semestre}",
        query_function=query_materias_semestre,
        query_params={},
        page_size=page_size,
    )

    return {
        "semestre": semestre,
        "data": results,
        "pagination": metadata,
    }


@router.get("/{materia_id}")
def get_materia(
    materia_id: int,
    include_grupos: bool = Query(False, description="Incluir grupos de la materia"),
    include_prerrequisitos: bool = Query(True, description="Incluir prerrequisitos"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver materia específica con detalles completos"""
    materia = db.query(Materia).filter(Materia.id == materia_id).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")

    # Datos básicos
    nivel = db.query(Nivel).filter(Nivel.id == materia.nivel_id).first()
    plan = (
        db.query(PlanEstudio).filter(PlanEstudio.id == materia.plan_estudio_id).first()
    )

    materia_data = {
        "id": materia.id,
        "sigla": materia.sigla,
        "nombre": materia.nombre,
        "creditos": materia.creditos,
        "es_electiva": materia.es_electiva,
        "nivel": (
            {
                "id": nivel.id,
                "nivel": nivel.nivel,
                "semestre": f"Semestre {nivel.nivel}",
            }
            if nivel
            else None
        ),
        "plan_estudio": (
            {
                "id": plan.id,
                "codigo": plan.codigo,
                "plan": plan.plan,
                "carrera_id": plan.carrera_id,
            }
            if plan
            else None
        ),
        "created_at": materia.created_at.isoformat() if materia.created_at else None,
        "updated_at": materia.updated_at.isoformat() if materia.updated_at else None,
    }

    # Incluir prerrequisitos
    if include_prerrequisitos:
        prerrequisitos = (
            db.query(Prerrequisito).filter(Prerrequisito.materia_id == materia.id).all()
        )
        materia_data["prerrequisitos"] = [
            {
                "id": p.id,
                "sigla_prerrequisito": p.sigla_prerrequisito,
            }
            for p in prerrequisitos
        ]

    # Incluir grupos si se solicita
    if include_grupos:
        grupos = db.query(Grupo).filter(Grupo.materia_id == materia.id).limit(20).all()
        materia_data["grupos"] = [
            {
                "id": g.id,
                "descripcion": g.descripcion,
                "docente_id": g.docente_id,
                "gestion_id": g.gestion_id,
            }
            for g in grupos
        ]

    # Estadísticas
    grupos_count = db.query(Grupo).filter(Grupo.materia_id == materia.id).count()
    materia_data["statistics"] = {
        "total_grupos": grupos_count,
        "prerrequisitos_count": len(materia_data.get("prerrequisitos", [])),
    }

    return materia_data


@router.post("/")
def create_materia(
    materia_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear materia (procesamiento síncrono)"""
    try:
        # Validar campos requeridos
        required_fields = ["sigla", "nombre", "creditos", "nivel_id", "plan_estudio_id"]
        missing_fields = [
            field for field in required_fields if field not in materia_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que la sigla no exista
        existing = (
            db.query(Materia).filter(Materia.sigla == materia_data["sigla"]).first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe una materia con la sigla '{materia_data['sigla']}'",
            )

        # Verificar que el nivel existe
        nivel = db.query(Nivel).filter(Nivel.id == materia_data["nivel_id"]).first()
        if not nivel:
            raise HTTPException(status_code=400, detail="Nivel especificado no existe")

        # Verificar que el plan de estudios existe
        plan = (
            db.query(PlanEstudio)
            .filter(PlanEstudio.id == materia_data["plan_estudio_id"])
            .first()
        )
        if not plan:
            raise HTTPException(
                status_code=400, detail="Plan de estudios especificado no existe"
            )

        # Configurar rollback
        rollback_data = {
            "operation": "create",
            "table": "materias",
            "created_by": current_user.id,
        }

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_materia",
            data=materia_data,
            priority=priority,
            max_retries=3,
            rollback_data=rollback_data,
        )

        return {
            "task_id": task_id,
            "message": "Materia en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "check_status": f"/queue/tasks/{task_id}",
            "estimated_processing": "1-3 segundos",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{materia_id}")
def update_materia(
    materia_id: int,
    materia_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Actualizar materia (procesamiento síncrono con rollback)"""
    try:
        # Verificar que existe
        existing_materia = db.query(Materia).filter(Materia.id == materia_id).first()
        if not existing_materia:
            raise HTTPException(status_code=404, detail="Materia no encontrada")

        # Verificar sigla única si se está cambiando
        if "sigla" in materia_data and materia_data["sigla"] != existing_materia.sigla:
            sigla_exists = (
                db.query(Materia)
                .filter(
                    Materia.sigla == materia_data["sigla"], Materia.id != materia_id
                )
                .first()
            )
            if sigla_exists:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe una materia con la sigla '{materia_data['sigla']}'",
                )

        # Verificar referencias si se están cambiando
        if "nivel_id" in materia_data:
            nivel = db.query(Nivel).filter(Nivel.id == materia_data["nivel_id"]).first()
            if not nivel:
                raise HTTPException(
                    status_code=400, detail="Nivel especificado no existe"
                )

        if "plan_estudio_id" in materia_data:
            plan = (
                db.query(PlanEstudio)
                .filter(PlanEstudio.id == materia_data["plan_estudio_id"])
                .first()
            )
            if not plan:
                raise HTTPException(
                    status_code=400, detail="Plan de estudios especificado no existe"
                )

        # Agregar ID a los datos
        materia_data["id"] = materia_id

        # Configurar rollback con estado original
        rollback_data = {
            "operation": "update",
            "table": "materias",
            "record_id": materia_id,
            "original_data": {
                "sigla": existing_materia.sigla,
                "nombre": existing_materia.nombre,
                "creditos": existing_materia.creditos,
                "es_electiva": existing_materia.es_electiva,
                "nivel_id": existing_materia.nivel_id,
                "plan_estudio_id": existing_materia.plan_estudio_id,
            },
            "updated_by": current_user.id,
        }

        task_id = sync_thread_queue_manager.add_task(
            task_type="update_materia",
            data=materia_data,
            priority=priority,
            max_retries=3,
            rollback_data=rollback_data,
        )

        return {
            "task_id": task_id,
            "message": "Actualización en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "materia_id": materia_id,
            "check_status": f"/queue/tasks/{task_id}",
            "rollback_available": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{materia_id}")
def delete_materia(
    materia_id: int,
    force: bool = Query(False, description="Forzar eliminación aunque tenga grupos"),
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Eliminar materia (procesamiento síncrono)"""
    try:
        # Verificar que existe
        materia = db.query(Materia).filter(Materia.id == materia_id).first()
        if not materia:
            raise HTTPException(status_code=404, detail="Materia no encontrada")

        # Verificar si tiene grupos
        grupos_count = db.query(Grupo).filter(Grupo.materia_id == materia_id).count()
        if grupos_count > 0 and not force:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede eliminar la materia porque tiene {grupos_count} grupos asociados. Use force=true para forzar la eliminación.",
            )

        # Verificar prerrequisitos
        prerrequisitos_count = (
            db.query(Prerrequisito)
            .filter(Prerrequisito.materia_id == materia_id)
            .count()
        )

        task_id = sync_thread_queue_manager.add_task(
            task_type="delete_materia",
            data={"id": materia_id, "force": force},
            priority=priority,
            max_retries=2,
        )

        return {
            "task_id": task_id,
            "message": "Eliminación en cola de procesamiento",
            "status": "pending",
            "priority": priority,
            "materia_id": materia_id,
            "groups_affected": grupos_count if force else 0,
            "prerrequisitos_affected": prerrequisitos_count,
            "check_status": f"/queue/tasks/{task_id}",
            "warning": "Esta operación no se puede deshacer"
            + (
                f" y afectará a {grupos_count} grupos y {prerrequisitos_count} prerrequisitos"
                if force and (grupos_count > 0 or prerrequisitos_count > 0)
                else ""
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/sigla/{sigla}")
def search_materia_by_sigla(
    sigla: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Buscar materia por sigla exacta"""
    materia = db.query(Materia).filter(Materia.sigla.ilike(sigla)).first()
    if not materia:
        raise HTTPException(
            status_code=404, detail=f"No se encontró materia con sigla '{sigla}'"
        )

    # Obtener información adicional
    nivel = db.query(Nivel).filter(Nivel.id == materia.nivel_id).first()
    grupos_count = db.query(Grupo).filter(Grupo.materia_id == materia.id).count()
    prerrequisitos = (
        db.query(Prerrequisito).filter(Prerrequisito.materia_id == materia.id).all()
    )

    return {
        "id": materia.id,
        "sigla": materia.sigla,
        "nombre": materia.nombre,
        "creditos": materia.creditos,
        "es_electiva": materia.es_electiva,
        "semestre": nivel.nivel if nivel else None,
        "grupos_count": grupos_count,
        "prerrequisitos": [p.sigla_prerrequisito for p in prerrequisitos],
        "created_at": materia.created_at.isoformat() if materia.created_at else None,
    }


@router.get("/{materia_id}/grupos")
def get_materia_grupos(
    materia_id: int,
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener grupos de una materia específica con paginación"""
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
        return [
            {
                "id": g.id,
                "descripcion": g.descripcion,
                "docente_id": g.docente_id,
                "gestion_id": g.gestion_id,
                "horario_id": g.horario_id,
            }
            for g in grupos
        ]

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint=f"materia_{materia_id}_grupos",
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
