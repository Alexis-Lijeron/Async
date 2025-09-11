from pydantic import BaseModel, ConfigDict
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .horario import Horario


class AulaBase(BaseModel):
    modulo: str
    aula: str


class AulaCreate(AulaBase):
    pass


class AulaUpdate(BaseModel):
    modulo: Optional[str] = None
    aula: Optional[str] = None


class AulaInDB(AulaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class Aula(AulaInDB):
    pass


class AulaWithRelations(Aula):
    horarios: Optional[List["Horario"]] = []
