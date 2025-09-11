from pydantic import BaseModel, ConfigDict
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .carrera import Carrera
    from .inscripcion import Inscripcion
    from .nota import Nota


class EstudianteBase(BaseModel):
    registro: str
    nombre: str
    apellido: str
    ci: str
    carrera_id: int


class EstudianteCreate(EstudianteBase):
    contraseña: str


class EstudianteUpdate(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    ci: Optional[str] = None
    carrera_id: Optional[int] = None


class EstudianteInDB(EstudianteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class Estudiante(EstudianteInDB):
    pass


class EstudianteWithRelations(Estudiante):
    carrera: Optional["Carrera"] = None
    inscripciones: Optional[List["Inscripcion"]] = []
    notas: Optional[List["Nota"]] = []
