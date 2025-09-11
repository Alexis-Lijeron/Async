from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.inscripcion import Inscripcion
from app.schemas.inscripcion import InscripcionCreate, InscripcionUpdate


class CRUDInscripcion(CRUDBase[Inscripcion, InscripcionCreate, InscripcionUpdate]):
    async def get_by_estudiante(
        self, db: AsyncSession, estudiante_id: int, skip: int = 0, limit: int = 100
    ) -> List[Inscripcion]:
        result = await db.execute(
            select(Inscripcion)
            .where(Inscripcion.estudiante_id == estudiante_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_estudiante_with_relations(
        self, db: AsyncSession, estudiante_id: int, skip: int = 0, limit: int = 100
    ) -> List[Inscripcion]:
        result = await db.execute(
            select(Inscripcion)
            .options(
                selectinload(Inscripcion.gestion),
                selectinload(Inscripcion.grupo),
                selectinload(Inscripcion.estudiante),
            )
            .where(Inscripcion.estudiante_id == estudiante_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_grupo(
        self, db: AsyncSession, grupo_id: int, skip: int = 0, limit: int = 100
    ) -> List[Inscripcion]:
        result = await db.execute(
            select(Inscripcion)
            .where(Inscripcion.grupo_id == grupo_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_estudiante_grupo(
        self, db: AsyncSession, estudiante_id: int, grupo_id: int
    ) -> Optional[Inscripcion]:
        result = await db.execute(
            select(Inscripcion).where(
                (Inscripcion.estudiante_id == estudiante_id)
                & (Inscripcion.grupo_id == grupo_id)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_gestion(
        self, db: AsyncSession, gestion_id: int, skip: int = 0, limit: int = 100
    ) -> List[Inscripcion]:
        result = await db.execute(
            select(Inscripcion)
            .where(Inscripcion.gestion_id == gestion_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()


inscripcion = CRUDInscripcion(Inscripcion)
