from pydantic import BaseModel, ConfigDict
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .estudiante import Estudiante
    from .plan_estudio import PlanEstudio


class CarreraBase(BaseModel):
    codigo: str
    nombre: str


class CarreraCreate(CarreraBase):
    pass


class CarreraUpdate(BaseModel):
    codigo: Optional[str] = None
    nombre: Optional[str] = None


class CarreraInDB(CarreraBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class Carrera(CarreraInDB):
    pass


class CarreraWithRelations(Carrera):
    estudiantes: Optional[List["Estudiante"]] = []
    planes_estudio: Optional[List["PlanEstudio"]] = []
