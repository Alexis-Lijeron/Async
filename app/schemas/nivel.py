from pydantic import BaseModel, ConfigDict
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .materia import Materia


class NivelBase(BaseModel):
    nivel: int


class NivelCreate(NivelBase):
    pass


class NivelUpdate(BaseModel):
    nivel: Optional[int] = None


class NivelInDB(NivelBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class Nivel(NivelInDB):
    pass


class NivelWithRelations(Nivel):
    materias: Optional[List["Materia"]] = []
