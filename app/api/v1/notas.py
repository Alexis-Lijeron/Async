from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.config.database import get_db
from app.models.nota import Nota
from app.models.estudiante import Estudiante
from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator

router = APIRouter()


@router.get("/")
def get_notas(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    estudiante_id: Optional[int] = Query(None, description="Filtrar por estudiante"),
    min_nota: Optional[float] = Query(None, description="Nota mínima"),
    max_nota: Optional[float] = Query(None, description="Nota máxima"),
    estado: Optional[str] = Query(
        None, description="Filtrar por estado (aprobado/reprobado)"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lista de notas con paginación inteligente (SÍNCRONO)"""

    def query_notas(db: Session, offset: int, limit: int, **kwargs):
        query = db.query(Nota)

        if estudiante_id:
            query = query.filter(Nota.estudiante_id == estudiante_id)
        if min_nota is not None:
            query = query.filter(Nota.nota >= min_nota)
        if max_nota is not None:
            query = query.filter(Nota.nota <= max_nota)
        if estado:
            if estado.lower() == "aprobado":
                query = query.filter(Nota.nota >= 61)
            elif estado.lower() == "reprobado":
                query = query.filter(Nota.nota < 61)

        notas = query.offset(offset).limit(limit).all()

        result = []
        for n in notas:
            estudiante = (
                db.query(Estudiante).filter(Estudiante.id == n.estudiante_id).first()
            )

            estado_nota = "Aprobado" if n.nota >= 61 else "Reprobado"
            color_estado = "success" if n.nota >= 61 else "danger"

            result.append(
                {
                    "id": n.id,
                    "nota": n.nota,
                    "estado": estado_nota,
                    "color_estado": color_estado,
                    "es_aprobado": n.nota >= 61,
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
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="notas_list",
        query_function=query_notas,
        query_params={
            "estudiante_id": estudiante_id,
            "min_nota": min_nota,
            "max_nota": max_nota,
            "estado": estado,
        },
        page_size=page_size,
    )

    return {
        "data": results,
        "pagination": metadata,
        "filters": {
            "estudiante_id": estudiante_id,
            "min_nota": min_nota,
            "max_nota": max_nota,
            "estado": estado,
        },
    }


@router.get("/mis-notas")
def get_mis_notas(
    session_id: Optional[str] = Query(None, description="ID de sesión para paginación"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Mis notas del estudiante actual con paginación"""

    def query_mis_notas(db: Session, offset: int, limit: int, **kwargs):
        notas = (
            db.query(Nota)
            .filter(Nota.estudiante_id == current_user.id)
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for n in notas:
            estado_nota = "Aprobado" if n.nota >= 61 else "Reprobado"
            color_estado = "success" if n.nota >= 61 else "danger"

            result.append(
                {
                    "id": n.id,
                    "nota": n.nota,
                    "estado": estado_nota,
                    "color_estado": color_estado,
                    "es_aprobado": n.nota >= 61,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
            )

        return result

    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    results, metadata = sync_smart_paginator.get_next_page(
        session_id=session_id,
        endpoint="mis_notas",
        query_function=query_mis_notas,
        query_params={},
        page_size=page_size,
    )

    # Calcular estadísticas del estudiante
    todas_notas = db.query(Nota).filter(Nota.estudiante_id == current_user.id).all()
    if todas_notas:
        promedio = sum(n.nota for n in todas_notas) / len(todas_notas)
        aprobadas = sum(1 for n in todas_notas if n.nota >= 61)
        reprobadas = len(todas_notas) - aprobadas
    else:
        promedio = 0
        aprobadas = 0
        reprobadas = 0

    return {
        "data": results,
        "pagination": metadata,
        "estudiante": {
            "id": current_user.id,
            "registro": current_user.registro,
            "nombre_completo": f"{current_user.nombre} {current_user.apellido}",
        },
        "estadisticas": {
            "total_notas": len(todas_notas),
            "promedio": round(promedio, 2),
            "materias_aprobadas": aprobadas,
            "materias_reprobadas": reprobadas,
            "porcentaje_aprobacion": (
                round((aprobadas / len(todas_notas) * 100), 2) if todas_notas else 0
            ),
        },
    }


@router.get("/{nota_id}")
def get_nota(
    nota_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Ver nota específica con detalles"""
    nota = db.query(Nota).filter(Nota.id == nota_id).first()
    if not nota:
        raise HTTPException(status_code=404, detail="Nota no encontrada")

    estudiante = (
        db.query(Estudiante).filter(Estudiante.id == nota.estudiante_id).first()
    )

    return {
        "id": nota.id,
        "nota": nota.nota,
        "estado": "Aprobado" if nota.nota >= 61 else "Reprobado",
        "es_aprobado": nota.nota >= 61,
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
        "created_at": nota.created_at.isoformat() if nota.created_at else None,
        "updated_at": nota.updated_at.isoformat() if nota.updated_at else None,
    }


@router.post("/")
def create_nota(
    nota_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Crear nota"""
    try:
        required_fields = ["nota", "estudiante_id"]
        missing_fields = [field for field in required_fields if field not in nota_data]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            )

        # Validar nota
        if not (0 <= nota_data["nota"] <= 100):
            raise HTTPException(
                status_code=400,
                detail="La nota debe estar entre 0 y 100",
            )

        # Verificar que el estudiante existe
        if (
            not db.query(Estudiante)
            .filter(Estudiante.id == nota_data["estudiante_id"])
            .first()
        ):
            raise HTTPException(status_code=400, detail="Estudiante no encontrado")

        task_id = sync_thread_queue_manager.add_task(
            task_type="create_nota",
            data=nota_data,
            priority=priority,
            max_retries=3,
        )

        return {
            "task_id": task_id,
            "message": "Nota en cola de procesamiento",
            "status": "pending",
            "check_status": f"/queue/tasks/{task_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{nota_id}")
def update_nota(
    nota_id: int,
    nota_data: dict,
    priority: int = Query(5, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Actualizar nota"""
    nota_data["id"] = nota_id
    task_id = sync_thread_queue_manager.add_task(
        "update_nota", nota_data, priority=priority
    )
    return {"task_id": task_id, "message": "Actualización en cola", "status": "pending"}


@router.delete("/{nota_id}")
def delete_nota(
    nota_id: int,
    priority: int = Query(3, ge=1, le=10, description="Prioridad de la tarea"),
    current_user=Depends(get_current_active_user),
):
    """Eliminar nota"""
    task_id = sync_thread_queue_manager.add_task(
        "delete_nota", {"id": nota_id}, priority=priority
    )
    return {"task_id": task_id, "message": "Eliminación en cola", "status": "pending"}


@router.get("/estadisticas/resumen")
def get_estadisticas_notas(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Obtener estadísticas generales de notas"""
    from sqlalchemy import func

    total_notas = db.query(Nota).count()

    if total_notas == 0:
        return {
            "total_notas": 0,
            "promedio_general": 0,
            "aprobados": 0,
            "reprobados": 0,
            "porcentaje_aprobacion": 0,
        }

    # Estadísticas básicas
    promedio_result = db.query(func.avg(Nota.nota)).scalar()
    promedio_general = float(promedio_result) if promedio_result else 0

    aprobados = db.query(Nota).filter(Nota.nota >= 61).count()
    reprobados = total_notas - aprobados

    # Distribución por rangos
    excelente = db.query(Nota).filter(Nota.nota >= 90).count()  # 90-100
    bueno = db.query(Nota).filter(Nota.nota >= 80, Nota.nota < 90).count()  # 80-89
    regular = db.query(Nota).filter(Nota.nota >= 61, Nota.nota < 80).count()  # 61-79
    deficiente = db.query(Nota).filter(Nota.nota < 61).count()  # 0-60

    return {
        "total_notas": total_notas,
        "promedio_general": round(promedio_general, 2),
        "aprobados": aprobados,
        "reprobados": reprobados,
        "porcentaje_aprobacion": round((aprobados / total_notas * 100), 2),
        "distribucion": {
            "excelente_90_100": excelente,
            "bueno_80_89": bueno,
            "regular_61_79": regular,
            "deficiente_0_60": deficiente,
        },
        "porcentajes_distribucion": {
            "excelente": round((excelente / total_notas * 100), 2),
            "bueno": round((bueno / total_notas * 100), 2),
            "regular": round((regular / total_notas * 100), 2),
            "deficiente": round((deficiente / total_notas * 100), 2),
        },
    }
