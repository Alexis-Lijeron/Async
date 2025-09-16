from pydantic import BaseModel, ConfigDict
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .docente import Docente
    from .gestion import Gestion
    from .materia import Materia
    from .horario import Horario
    from .inscripcion import Inscripcion
    from .detalle import Detalle


class GrupoBase(BaseModel):
    codigo_grupo: str  # NUEVO
    descripcion: str
    docente_id: int
    gestion_id: int
    materia_id: int
    horario_id: int


class GrupoCreate(GrupoBase):
    pass


class GrupoUpdate(BaseModel):
    codigo_grupo: Optional[str] = None  # NUEVO
    descripcion: Optional[str] = None
    docente_id: Optional[int] = None
    gestion_id: Optional[int] = None
    materia_id: Optional[int] = None
    horario_id: Optional[int] = None


class GrupoInDB(GrupoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class Grupo(GrupoInDB):
    pass


class GrupoWithRelations(Grupo):
    docente: Optional["Docente"] = None
    gestion: Optional["Gestion"] = None
    materia: Optional["Materia"] = None
    horario: Optional["Horario"] = None
    inscripciones: Optional[List["Inscripcion"]] = []
    detalles: Optional[List["Detalle"]] = []
