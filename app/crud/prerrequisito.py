from typing import Optional, List
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.prerrequisito import Prerrequisito
from app.schemas.prerrequisito import PrerrequisiteCreate, PrerrequisiteUpdate


class CRUDPrerrequisito(
    CRUDBase[Prerrequisito, PrerrequisiteCreate, PrerrequisiteUpdate]
):
    def get_with_relations(self, db: Session, id: int) -> Optional[Prerrequisito]:
        return (
            db.query(Prerrequisito)
            .options(joinedload(Prerrequisito.materia))
            .filter(Prerrequisito.id == id)
            .first()
        )

    def get_by_materia(self, db: Session, materia_id: int) -> List[Prerrequisito]:
        """Obtener todos los prerrequisitos de una materia"""
        return (
            db.query(Prerrequisito).filter(Prerrequisito.materia_id == materia_id).all()
        )

    def get_by_sigla_prerrequisito(
        self, db: Session, sigla: str
    ) -> List[Prerrequisito]:
        """Obtener todas las materias que tienen esta sigla como prerrequisito"""
        return (
            db.query(Prerrequisito)
            .filter(Prerrequisito.sigla_prerrequisito == sigla)
            .all()
        )

    def get_materia_prerrequisito(
        self, db: Session, materia_id: int, sigla_prerrequisito: str
    ) -> Optional[Prerrequisito]:
        """Verificar si existe un prerrequisito específico"""
        return (
            db.query(Prerrequisito)
            .filter(
                Prerrequisito.materia_id == materia_id,
                Prerrequisito.sigla_prerrequisito == sigla_prerrequisito,
            )
            .first()
        )

    def get_prereq_chain(self, db: Session, materia_id: int) -> List[dict]:
        """Obtener cadena completa de prerrequisitos de una materia"""
        from app.models.materia import Materia

        prerrequisitos = self.get_by_materia(db, materia_id)
        chain = []

        for prereq in prerrequisitos:
            # Buscar la materia prerrequisito
            materia_prereq = (
                db.query(Materia)
                .filter(Materia.sigla == prereq.sigla_prerrequisito)
                .first()
            )

            prereq_info = {
                "id": prereq.id,
                "sigla_prerrequisito": prereq.sigla_prerrequisito,
                "materia_prerrequisito": (
                    {
                        "id": materia_prereq.id,
                        "nombre": materia_prereq.nombre,
                        "creditos": materia_prereq.creditos,
                    }
                    if materia_prereq
                    else None
                ),
            }

            # Recursivamente obtener prerrequisitos del prerrequisito
            if materia_prereq:
                sub_prereq = self.get_prereq_chain(db, materia_prereq.id)
                prereq_info["sub_prerrequisitos"] = sub_prereq

            chain.append(prereq_info)

        return chain

    def validate_circular_dependency(
        self, db: Session, materia_id: int, sigla_prerrequisito: str
    ) -> bool:
        """Validar que no se cree una dependencia circular"""
        from app.models.materia import Materia

        # Encontrar la materia prerrequisito
        materia_prereq = (
            db.query(Materia).filter(Materia.sigla == sigla_prerrequisito).first()
        )

        if not materia_prereq:
            return True  # No hay materia, no hay dependencia circular

        # Obtener la materia principal
        materia_principal = db.query(Materia).filter(Materia.id == materia_id).first()
        if not materia_principal:
            return False

        # Verificar si la materia prerrequisito depende de la materia principal
        def check_dependency(
            current_materia_id: int, target_sigla: str, visited: set
        ) -> bool:
            if current_materia_id in visited:
                return False

            visited.add(current_materia_id)

            prereqs = self.get_by_materia(db, current_materia_id)
            for prereq in prereqs:
                if prereq.sigla_prerrequisito == target_sigla:
                    return True

                # Buscar la materia del prerrequisito
                sub_materia = (
                    db.query(Materia)
                    .filter(Materia.sigla == prereq.sigla_prerrequisito)
                    .first()
                )

                if sub_materia and check_dependency(
                    sub_materia.id, target_sigla, visited
                ):
                    return True

            return False

        # Verificar si hay dependencia circular
        return not check_dependency(materia_prereq.id, materia_principal.sigla, set())

    def get_materias_dependientes(self, db: Session, sigla: str) -> List[dict]:
        """Obtener todas las materias que dependen de una sigla específica"""
        from app.models.materia import Materia

        prerrequisitos = self.get_by_sigla_prerrequisito(db, sigla)
        materias_dependientes = []

        for prereq in prerrequisitos:
            materia = db.query(Materia).filter(Materia.id == prereq.materia_id).first()
            if materia:
                materias_dependientes.append(
                    {
                        "prerrequisito_id": prereq.id,
                        "materia": {
                            "id": materia.id,
                            "sigla": materia.sigla,
                            "nombre": materia.nombre,
                            "nivel_id": materia.nivel_id,
                        },
                    }
                )

        return materias_dependientes


prerrequisito = CRUDPrerrequisito(Prerrequisito)
