from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.docente import Docente
from app.schemas.docente import DocenteCreate, DocenteUpdate


class CRUDDocente(CRUDBase[Docente, DocenteCreate, DocenteUpdate]):
    async def get_with_relations(self, db: AsyncSession, id: int) -> Optional[Docente]:
        result = await db.execute(
            select(Docente)
            .options(selectinload(Docente.grupos))
            .where(Docente.id == id)
        )
        return result.scalar_one_or_none()

    async def search_by_name(
        self, db: AsyncSession, name: str, skip: int = 0, limit: int = 100
    ):
        result = await db.execute(
            select(Docente)
            .where(
                (Docente.nombre.ilike(f"%{name}%"))
                | (Docente.apellido.ilike(f"%{name}%"))
            )
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()


docente = CRUDDocente(Docente)
