from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.crud.base import CRUDBase
from app.models.nota import Nota
from app.schemas.nota import NotaCreate, NotaUpdate


class CRUDNota(CRUDBase[Nota, NotaCreate, NotaUpdate]):
    def get_with_relations(self, db: Session, id: int) -> Optional[Nota]:
        return (
            db.query(Nota)
            .options(joinedload(Nota.estudiante))
            .filter(Nota.id == id)
            .first()
        )

    def get_by_estudiante(
        self, db: Session, estudiante_id: int, skip: int = 0, limit: int = 100
    ) -> List[Nota]:
        return (
            db.query(Nota)
            .filter(Nota.estudiante_id == estudiante_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_range(
        self,
        db: Session,
        min_nota: float,
        max_nota: float,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Nota]:
        return (
            db.query(Nota)
            .filter(Nota.nota >= min_nota, Nota.nota <= max_nota)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_aprobadas(self, db: Session, skip: int = 0, limit: int = 100) -> List[Nota]:
        """Obtener notas aprobadas (>= 61)"""
        return db.query(Nota).filter(Nota.nota >= 61).offset(skip).limit(limit).all()

    def get_reprobadas(
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> List[Nota]:
        """Obtener notas reprobadas (< 61)"""
        return db.query(Nota).filter(Nota.nota < 61).offset(skip).limit(limit).all()

    def get_estadisticas_estudiante(self, db: Session, estudiante_id: int) -> dict:
        """Obtener estadísticas de un estudiante"""
        notas = self.get_by_estudiante(db, estudiante_id)

        if not notas:
            return {
                "total_notas": 0,
                "promedio": 0,
                "nota_maxima": 0,
                "nota_minima": 0,
                "aprobadas": 0,
                "reprobadas": 0,
                "porcentaje_aprobacion": 0,
            }

        total_notas = len(notas)
        promedio = sum(n.nota for n in notas) / total_notas
        nota_maxima = max(n.nota for n in notas)
        nota_minima = min(n.nota for n in notas)
        aprobadas = sum(1 for n in notas if n.nota >= 61)
        reprobadas = total_notas - aprobadas
        porcentaje_aprobacion = (
            (aprobadas / total_notas * 100) if total_notas > 0 else 0
        )

        return {
            "total_notas": total_notas,
            "promedio": round(promedio, 2),
            "nota_maxima": nota_maxima,
            "nota_minima": nota_minima,
            "aprobadas": aprobadas,
            "reprobadas": reprobadas,
            "porcentaje_aprobacion": round(porcentaje_aprobacion, 2),
        }

    def get_estadisticas_generales(self, db: Session) -> dict:
        """Obtener estadísticas generales del sistema"""
        total_count = db.query(func.count(Nota.id)).scalar()

        if total_count == 0:
            return {
                "total_notas": 0,
                "promedio_general": 0,
                "aprobadas": 0,
                "reprobadas": 0,
                "porcentaje_aprobacion": 0,
            }

        promedio_general = db.query(func.avg(Nota.nota)).scalar()
        aprobadas = db.query(func.count(Nota.id)).filter(Nota.nota >= 61).scalar()
        reprobadas = total_count - aprobadas
        porcentaje_aprobacion = (
            (aprobadas / total_count * 100) if total_count > 0 else 0
        )

        return {
            "total_notas": total_count,
            "promedio_general": round(float(promedio_general), 2),
            "aprobadas": aprobadas,
            "reprobadas": reprobadas,
            "porcentaje_aprobacion": round(porcentaje_aprobacion, 2),
        }

    def get_top_estudiantes(self, db: Session, limit: int = 10) -> List[dict]:
        """Obtener top estudiantes por promedio"""
        from app.models.estudiante import Estudiante

        result = (
            db.query(
                Estudiante.id,
                Estudiante.registro,
                Estudiante.nombre,
                Estudiante.apellido,
                func.avg(Nota.nota).label("promedio"),
                func.count(Nota.id).label("total_notas"),
            )
            .join(Nota, Estudiante.id == Nota.estudiante_id)
            .group_by(Estudiante.id)
            .order_by(func.avg(Nota.nota).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "estudiante_id": r.id,
                "registro": r.registro,
                "nombre_completo": f"{r.nombre} {r.apellido}",
                "promedio": round(float(r.promedio), 2),
                "total_notas": r.total_notas,
            }
            for r in result
        ]


nota = CRUDNota(Nota)
