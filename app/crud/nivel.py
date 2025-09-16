from typing import Optional, List
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.nivel import Nivel
from app.schemas.nivel import NivelCreate, NivelUpdate


class CRUDNivel(CRUDBase[Nivel, NivelCreate, NivelUpdate]):
    def get_by_nivel(self, db: Session, *, nivel: int) -> Optional[Nivel]:
        return db.query(Nivel).filter(Nivel.nivel == nivel).first()

    def get_with_relations(self, db: Session, id: int) -> Optional[Nivel]:
        return (
            db.query(Nivel)
            .options(joinedload(Nivel.materias))
            .filter(Nivel.id == id)
            .first()
        )

    def get_all_ordered(self, db: Session) -> List[Nivel]:
        """Obtener todos los niveles ordenados por número de nivel"""
        return db.query(Nivel).order_by(Nivel.nivel.asc()).all()

    def get_range(self, db: Session, min_nivel: int, max_nivel: int) -> List[Nivel]:
        """Obtener niveles en un rango específico"""
        return (
            db.query(Nivel)
            .filter(Nivel.nivel >= min_nivel, Nivel.nivel <= max_nivel)
            .order_by(Nivel.nivel.asc())
            .all()
        )

    def get_with_materias_count(self, db: Session) -> List[dict]:
        """Obtener niveles con el conteo de materias"""
        from sqlalchemy import func
        from app.models.materia import Materia

        result = (
            db.query(
                Nivel.id, Nivel.nivel, func.count(Materia.id).label("materias_count")
            )
            .outerjoin(Materia, Nivel.id == Materia.nivel_id)
            .group_by(Nivel.id, Nivel.nivel)
            .order_by(Nivel.nivel.asc())
            .all()
        )

        return [
            {"id": r.id, "nivel": r.nivel, "materias_count": r.materias_count}
            for r in result
        ]


nivel = CRUDNivel(Nivel)
