from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.prerrequisito import Prerrequisito
from app.models.materia import Materia
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_prerrequisitos(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    materia_id: Optional[int] = Query(None, description="Filtrar por materia"),
    sigla_prerrequisito: Optional[str] = Query(
        None, description="Filtrar por sigla de prerrequisito"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de prerrequisitos con paginación inteligente (SÍNCRONO)"""

    def query_prerrequisitos(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Prerrequisito)

        if materia_id:
            query = query.filter(Prerrequisito.materia_id == materia_id)

        if sigla_prerrequisito:
            query = query.filter(
                Prerrequisito.sigla_prerrequisito.ilike(f"%{sigla_prerrequisito}%")
            )

        prerrequisitos = query.offset(offset).limit(limit).all()

        result = []
        for p in prerrequisitos:
            # Obtener materia principal
            materia = db.query(Materia).filter(Materia.id == p.materia_id).first()

            # Obtener materia prerrequisito
            materia_prereq = (
                db.query(Materia).filter(Materia.sigla == p.sigla_prerrequisito).first()
            )

            result.append(
                {
                    "id": p.id,
                    "sigla_prerrequisito": p.sigla_prerrequisito,
                    "materia": (
                        {
                            "id": materia.id,
                            "sigla": materia.sigla,
                            "nombre": materia.nombre,
                            "nivel_id": materia.nivel_id,
                        }
                        if materia
                        else None
                    ),
                    "materia_prerrequisito": (
                        {
                            "id": materia_prereq.id,
                            "sigla": materia_prereq.sigla,
                            "nombre": materia_prereq.nombre,
                            "nivel_id": materia_prereq.nivel_id,
                        }
                        if materia_prereq
                        else None
                    ),
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="prerrequisitos_list",
        query_function=query_prerrequisitos,
        query_params={
            "materia_id": materia_id,
            "sigla_prerrequisito": sigla_prerrequisito,
        },
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {
            "materia_id": materia_id,
            "sigla_prerrequisito": sigla_prerrequisito,
        },
    }


@router.get("/{prerrequisito_id}")
def get_prerrequisito(
    prerrequisito_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver prerrequisito específico con detalles completos"""
    prerrequisito = (
        db.query(Prerrequisito).filter(Prerrequisito.id == prerrequisito_id).first()
    )
    if not prerrequisito:
        raise HTTPException(status_code=404, detail="Prerrequisito no encontrado")

    # Obtener materia principal
    materia = db.query(Materia).filter(Materia.id == prerrequisito.materia_id).first()

    # Obtener materia prerrequisito
    materia_prereq = (
        db.query(Materia)
        .filter(Materia.sigla == prerrequisito.sigla_prerrequisito)
        .first()
    )

    return {
        "id": prerrequisito.id,
        "sigla_prerrequisito": prerrequisito.sigla_prerrequisito,
        "materia": (
            {
                "id": materia.id,
                "sigla": materia.sigla,
                "nombre": materia.nombre,
                "creditos": materia.creditos,
                "nivel_id": materia.nivel_id,
                "es_electiva": materia.es_electiva,
            }
            if materia
            else None
        ),
        "materia_prerrequisito": (
            {
                "id": materia_prereq.id,
                "sigla": materia_prereq.sigla,
                "nombre": materia_prereq.nombre,
                "creditos": materia_prereq.creditos,
                "nivel_id": materia_prereq.nivel_id,
                "es_electiva": materia_prereq.es_electiva,
            }
            if materia_prereq
            else None
        ),
        "created_at": (
            prerrequisito.created_at.isoformat() if prerrequisito.created_at else None
        ),
        "updated_at": (
            prerrequisito.updated_at.isoformat() if prerrequisito.updated_at else None
        ),
    }


@router.post("/")
def create_prerrequisito(
    prerrequisito_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear prerrequisito"""
    try:
        required_fields = ["materia_id", "sigla_prerrequisito"]
        missing_fields = [
            field for field in required_fields if field not in prerrequisito_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Verificar que la materia existe
        materia = (
            db.query(Materia)
            .filter(Materia.id == prerrequisito_data["materia_id"])
            .first()
        )
        if not materia:
            raise HTTPException(status_code=400, detail="Materia no encontrada")

        # Verificar que la materia prerrequisito existe
        materia_prereq = (
            db.query(Materia)
            .filter(Materia.sigla == prerrequisito_data["sigla_prerrequisito"])
            .first()
        )
        if not materia_prereq:
            raise HTTPException(
                status_code=400,
                detail=f"Materia con sigla '{prerrequisito_data['sigla_prerrequisito']}' no encontrada",
            )

        # Verificar que no existe ya este prerrequisito
        existing = (
            db.query(Prerrequisito)
            .filter(
                Prerrequisito.materia_id == prerrequisito_data["materia_id"],
                Prerrequisito.sigla_prerrequisito
                == prerrequisito_data["sigla_prerrequisito"],
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe este prerrequisito para la materia {materia.sigla}",
            )

        # Verificar dependencia circular usando el CRUD
        from app.crud.prerrequisito import prerrequisito as prereq_crud

        if not prereq_crud.validate_circular_dependency(
            db,
            prerrequisito_data["materia_id"],
            prerrequisito_data["sigla_prerrequisito"],
        ):
            raise HTTPException(
                status_code=400,
                detail="No se puede crear el prerrequisito: genera una dependencia circular",
            )

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_prerrequisito",
            data=prerrequisito_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Prerrequisito en cola de procesamiento",
            "status": "pending",
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{prerrequisito_id}")
def update_prerrequisito(
    prerrequisito_id: int,
    prerrequisito_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Actualizar prerrequisito"""
    prerrequisito_data["id"] = prerrequisito_id
    task_id = sync_thread_queue_manager.add_task(
        "update_prerrequisito", prerrequisito_data, priority=priority
    )
    return {"task_id": task_id, "message": "Actualización en cola", "status": "pending"}


@router.delete("/{prerrequisito_id}")
def delete_prerrequisito(
    prerrequisito_id: int,
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Eliminar prerrequisito"""
    task_id = sync_thread_queue_manager.add_task(
        "delete_prerrequisito", {"id": prerrequisito_id}, priority=priority
    )
    return {"task_id": task_id, "message": "Eliminación en cola", "status": "pending"}


@router.get("/materia/{materia_id}")
def get_prerrequisitos_by_materia(
    materia_id: int,
    include_chain: bool = Query(
        False, description="Incluir cadena completa de prerrequisitos"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener prerrequisitos de una materia específica"""
    # Verificar que la materia existe
    materia = db.query(Materia).filter(Materia.id == materia_id).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")

    prerrequisitos = (
        db.query(Prerrequisito).filter(Prerrequisito.materia_id == materia_id).all()
    )

    result = {
        "materia": {
            "id": materia.id,
            "sigla": materia.sigla,
            "nombre": materia.nombre,
        },
        "prerrequisitos": [],
    }

    for p in prerrequisitos:
        materia_prereq = (
            db.query(Materia).filter(Materia.sigla == p.sigla_prerrequisito).first()
        )

        prereq_info = {
            "id": p.id,
            "sigla_prerrequisito": p.sigla_prerrequisito,
            "materia_prerrequisito": (
                {
                    "id": materia_prereq.id,
                    "nombre": materia_prereq.nombre,
                    "creditos": materia_prereq.creditos,
                    "nivel_id": materia_prereq.nivel_id,
                }
                if materia_prereq
                else None
            ),
        }

        result["prerrequisitos"].append(prereq_info)

    # Incluir cadena completa si se solicita
    if include_chain:
        from app.crud.prerrequisito import prerrequisito as prereq_crud

        result["cadena_completa"] = prereq_crud.get_prereq_chain(db, materia_id)

    return result


@router.get("/dependientes/{sigla}")
def get_materias_dependientes(
    sigla: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener materias que dependen de una sigla específica"""
    # Verificar que la materia con esa sigla existe
    materia_base = db.query(Materia).filter(Materia.sigla == sigla).first()
    if not materia_base:
        raise HTTPException(
            status_code=404, detail=f"Materia con sigla '{sigla}' no encontrada"
        )

    from app.crud.prerrequisito import prerrequisito as prereq_crud

    materias_dependientes = prereq_crud.get_materias_dependientes(db, sigla)

    return {
        "materia_base": {
            "id": materia_base.id,
            "sigla": materia_base.sigla,
            "nombre": materia_base.nombre,
        },
        "total_dependientes": len(materias_dependientes),
        "materias_dependientes": materias_dependientes,
    }


@router.post("/validate-circular")
def validate_circular_dependency(
    validation_data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Validar si un prerrequisito crearía una dependencia circular"""
    try:
        required_fields = ["materia_id", "sigla_prerrequisito"]
        missing_fields = [
            field for field in required_fields if field not in validation_data
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        from app.crud.prerrequisito import prerrequisito as prereq_crud

        is_valid = prereq_crud.validate_circular_dependency(
            db, validation_data["materia_id"], validation_data["sigla_prerrequisito"]
        )

        return {
            "valid": is_valid,
            "message": (
                "Prerrequisito válido" if is_valid else "Crearía dependencia circular"
            ),
            "materia_id": validation_data["materia_id"],
            "sigla_prerrequisito": validation_data["sigla_prerrequisito"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
