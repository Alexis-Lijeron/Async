from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from datetime import time

from app.crud.base import CRUDBase
from app.models.horario import Horario
from app.schemas.horario import HorarioCreate, HorarioUpdate


class CRUDHorario(CRUDBase[Horario, HorarioCreate, HorarioUpdate]):
    def get_with_relations(self, db: Session, id: int) -> Optional[Horario]:
        return (
            db.query(Horario)
            .options(joinedload(Horario.aula), joinedload(Horario.grupos))
            .filter(Horario.id == id)
            .first()
        )

    def get_by_dia(
        self, db: Session, dia: str, skip: int = 0, limit: int = 100
    ) -> List[Horario]:
        return (
            db.query(Horario)
            .filter(Horario.dia.ilike(f"%{dia}%"))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_aula(
        self, db: Session, aula_id: int, skip: int = 0, limit: int = 100
    ) -> List[Horario]:
        return (
            db.query(Horario)
            .filter(Horario.aula_id == aula_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_time_range(
        self,
        db: Session,
        hora_inicio: time,
        hora_final: time,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Horario]:
        return (
            db.query(Horario)
            .filter(
                Horario.hora_inicio >= hora_inicio, Horario.hora_final <= hora_final
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def check_conflict(
        self,
        db: Session,
        aula_id: int,
        dia: str,
        hora_inicio: time,
        hora_final: time,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """Verificar si hay conflicto de horarios en la misma aula"""
        query = db.query(Horario).filter(
            Horario.aula_id == aula_id,
            Horario.dia.ilike(dia),
            # Verificar solapamiento de horarios
            ((Horario.hora_inicio <= hora_inicio) & (Horario.hora_final > hora_inicio))
            | ((Horario.hora_inicio < hora_final) & (Horario.hora_final >= hora_final))
            | (
                (Horario.hora_inicio >= hora_inicio)
                & (Horario.hora_final <= hora_final)
            ),
        )

        if exclude_id:
            query = query.filter(Horario.id != exclude_id)

        return query.first() is not None

    def get_available_slots(self, db: Session, aula_id: int, dia: str) -> List[dict]:
        """Obtener slots de tiempo disponibles para un aula en un día"""
        occupied_horarios = (
            db.query(Horario)
            .filter(Horario.aula_id == aula_id, Horario.dia.ilike(dia))
            .order_by(Horario.hora_inicio)
            .all()
        )

        # Lógica básica para encontrar slots disponibles
        # (se puede expandir según necesidades específicas)
        return [
            {
                "hora_inicio": h.hora_inicio.strftime("%H:%M"),
                "hora_final": h.hora_final.strftime("%H:%M"),
                "occupied": True,
            }
            for h in occupied_horarios
        ]


horario = CRUDHorario(Horario)
