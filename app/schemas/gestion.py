from pydantic import BaseModel, ConfigDict
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .grupo import Grupo
    from .inscripcion import Inscripcion


class GestionBase(BaseModel):
    semestre: int
    año: int


class GestionCreate(GestionBase):
    pass


class GestionUpdate(BaseModel):
    semestre: Optional[int] = None
    año: Optional[int] = None


class GestionInDB(GestionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class Gestion(GestionInDB):
    pass


class GestionWithRelations(Gestion):
    grupos: Optional[List["Grupo"]] = []
    inscripciones: Optional[List["Inscripcion"]] = []
