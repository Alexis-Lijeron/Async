from pydantic import BaseModel, ConfigDict
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .estudiante import Estudiante


class NotaBase(BaseModel):
    nota: float
    estudiante_id: int


class NotaCreate(NotaBase):
    pass


class NotaUpdate(BaseModel):
    nota: Optional[float] = None
    estudiante_id: Optional[int] = None


class NotaInDB(NotaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class Nota(NotaInDB):
    pass


class NotaWithRelations(Nota):
    estudiante: Optional["Estudiante"] = None
