from pydantic import BaseModel, ConfigDict
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .grupo import Grupo


class DocenteBase(BaseModel):
    nombre: str
    apellido: str


class DocenteCreate(DocenteBase):
    pass


class DocenteUpdate(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None


class DocenteInDB(DocenteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class Docente(DocenteInDB):
    pass


class DocenteWithRelations(Docente):
    grupos: Optional[List["Grupo"]] = []
