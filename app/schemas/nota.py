from pydantic import BaseModel, ConfigDict
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .estudiante import Estudiante


class NotaBase(BaseModel):
    codigo_nota: str  # NUEVO
    nota: float
    estudiante_id: int


class NotaCreate(NotaBase):
    pass


class NotaUpdate(BaseModel):
    codigo_nota: Optional[str] = None  # NUEVO
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
