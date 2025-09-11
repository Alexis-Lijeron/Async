from pydantic import BaseModel, ConfigDict
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .gestion import Gestion
    from .estudiante import Estudiante
    from .grupo import Grupo


class InscripcionBase(BaseModel):
    semestre: int
    gestion_id: int
    estudiante_id: int
    grupo_id: int


class InscripcionCreate(InscripcionBase):
    pass


class InscripcionUpdate(BaseModel):
    semestre: Optional[int] = None
    gestion_id: Optional[int] = None
    estudiante_id: Optional[int] = None
    grupo_id: Optional[int] = None


class InscripcionInDB(InscripcionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class Inscripcion(InscripcionInDB):
    pass


class InscripcionWithRelations(Inscripcion):
    gestion: Optional["Gestion"] = None
    estudiante: Optional["Estudiante"] = None
    grupo: Optional["Grupo"] = None
