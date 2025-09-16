from typing import Optional, List
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.gestion import Gestion
from app.schemas.gestion import GestionCreate, GestionUpdate


class CRUDGestion(CRUDBase[Gestion, GestionCreate, GestionUpdate]):
    def get_by_semestre_año(
        self, db: Session, *, semestre: int, año: int
    ) -> Optional[Gestion]:
        return (
            db.query(Gestion)
            .filter(Gestion.semestre == semestre, Gestion.año == año)
            .first()
        )

    def get_with_relations(self, db: Session, id: int) -> Optional[Gestion]:
        return (
            db.query(Gestion)
            .options(joinedload(Gestion.grupos), joinedload(Gestion.inscripciones))
            .filter(Gestion.id == id)
            .first()
        )

    def get_by_año(
        self, db: Session, año: int, skip: int = 0, limit: int = 100
    ) -> List[Gestion]:
        return (
            db.query(Gestion).filter(Gestion.año == año).offset(skip).limit(limit).all()
        )

    def get_current_gestiones(
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> List[Gestion]:
        """Obtener gestiones del año actual"""
        from datetime import datetime

        current_year = datetime.now().year

        return (
            db.query(Gestion)
            .filter(Gestion.año == current_year)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_latest_gestion(self, db: Session) -> Optional[Gestion]:
        """Obtener la gestión más reciente"""
        return (
            db.query(Gestion)
            .order_by(Gestion.año.desc(), Gestion.semestre.desc())
            .first()
        )


gestion = CRUDGestion(Gestion)
