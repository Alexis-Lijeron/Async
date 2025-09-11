from pydantic import BaseModel, ConfigDict
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .carrera import Carrera
    from .materia import Materia


class PlanEstudioBase(BaseModel):
    codigo: str
    cant_semestre: int
    plan: str
    carrera_id: int


class PlanEstudioCreate(PlanEstudioBase):
    pass


class PlanEstudioUpdate(BaseModel):
    codigo: Optional[str] = None
    cant_semestre: Optional[int] = None
    plan: Optional[str] = None
    carrera_id: Optional[int] = None


class PlanEstudioInDB(PlanEstudioBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class PlanEstudio(PlanEstudioInDB):
    pass


class PlanEstudioWithRelations(PlanEstudio):
    carrera: Optional["Carrera"] = None
    materias: Optional[List["Materia"]] = []
