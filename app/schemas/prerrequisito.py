from pydantic import BaseModel, ConfigDict
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .materia import Materia


class PrerrequisiteBase(BaseModel):
    materia_id: int
    sigla_prerrequisito: str


class PrerrequisiteCreate(PrerrequisiteBase):
    pass


class PrerrequisiteUpdate(BaseModel):
    materia_id: Optional[int] = None
    sigla_prerrequisito: Optional[str] = None


class PrerrequisiteInDB(PrerrequisiteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class Prerrequisito(PrerrequisiteInDB):
    pass


class PrerrequisiteWithRelations(Prerrequisito):
    materia: Optional["Materia"] = None
    prerrequisito_materia: Optional["Materia"] = None
