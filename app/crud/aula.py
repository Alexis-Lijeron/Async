from typing import Optional, List
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.aula import Aula
from app.schemas.aula import AulaCreate, AulaUpdate


class CRUDAula(CRUDBase[Aula, AulaCreate, AulaUpdate]):
    def get_by_modulo_aula(
        self, db: Session, *, modulo: str, aula: str
    ) -> Optional[Aula]:
        return db.query(Aula).filter(Aula.modulo == modulo, Aula.aula == aula).first()

    def get_with_relations(self, db: Session, id: int) -> Optional[Aula]:
        return (
            db.query(Aula)
            .options(joinedload(Aula.horarios))
            .filter(Aula.id == id)
            .first()
        )

    def get_by_modulo(
        self, db: Session, modulo: str, skip: int = 0, limit: int = 100
    ) -> List[Aula]:
        return (
            db.query(Aula).filter(Aula.modulo == modulo).offset(skip).limit(limit).all()
        )

    def search_aulas(
        self, db: Session, search: str, skip: int = 0, limit: int = 100
    ) -> List[Aula]:
        search_pattern = f"%{search}%"
        return (
            db.query(Aula)
            .filter(
                (Aula.modulo.ilike(search_pattern)) | (Aula.aula.ilike(search_pattern))
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


aula = CRUDAula(Aula)
