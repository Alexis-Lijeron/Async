from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.carrera import Carrera
from app.schemas.carrera import CarreraCreate, CarreraUpdate


class CRUDCarrera(CRUDBase[Carrera, CarreraCreate, CarreraUpdate]):
    async def get_by_codigo(
        self, db: AsyncSession, *, codigo: str
    ) -> Optional[Carrera]:
        result = await db.execute(select(Carrera).where(Carrera.codigo == codigo))
        return result.scalar_one_or_none()

    async def get_with_relations(self, db: AsyncSession, id: int) -> Optional[Carrera]:
        result = await db.execute(
            select(Carrera)
            .options(
                selectinload(Carrera.estudiantes), selectinload(Carrera.planes_estudio)
            )
            .where(Carrera.id == id)
        )
        return result.scalar_one_or_none()


carrera = CRUDCarrera(Carrera)
