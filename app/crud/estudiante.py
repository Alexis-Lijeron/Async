from typing import Optional
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.estudiante import Estudiante
from app.schemas.estudiante import EstudianteCreate, EstudianteUpdate
from app.core.security import get_password_hash


class CRUDEstudiante(CRUDBase[Estudiante, EstudianteCreate, EstudianteUpdate]):
    def get_by_registro(self, db: Session, *, registro: str) -> Optional[Estudiante]:
        return db.query(Estudiante).filter(Estudiante.registro == registro).first()

    def get_by_ci(self, db: Session, *, ci: str) -> Optional[Estudiante]:
        return db.query(Estudiante).filter(Estudiante.ci == ci).first()

    def create(self, db: Session, *, obj_in: EstudianteCreate) -> Estudiante:
        hashed_password = get_password_hash(obj_in.contraseña)
        db_obj = Estudiante(
            registro=obj_in.registro,
            nombre=obj_in.nombre,
            apellido=obj_in.apellido,
            ci=obj_in.ci,
            contraseña=hashed_password,
            carrera_id=obj_in.carrera_id,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_with_relations(self, db: Session, id: int) -> Optional[Estudiante]:
        return (
            db.query(Estudiante)
            .options(
                joinedload(Estudiante.carrera),
                joinedload(Estudiante.inscripciones),
                joinedload(Estudiante.notas),
            )
            .filter(Estudiante.id == id)
            .first()
        )

    def get_estudiantes_by_carrera(
        self, db: Session, carrera_id: int, skip: int = 0, limit: int = 100
    ):
        return (
            db.query(Estudiante)
            .filter(Estudiante.carrera_id == carrera_id)
            .offset(skip)
            .limit(limit)
            .all()
        )


estudiante = CRUDEstudiante(Estudiante)
