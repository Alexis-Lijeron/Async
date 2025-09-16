from pydantic import BaseModel, ConfigDict
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, time

if TYPE_CHECKING:
    from .aula import Aula
    from .grupo import Grupo


class HorarioBase(BaseModel):
    codigo_horario: str  # NUEVO
    dia: str
    hora_inicio: time
    hora_final: time
    aula_id: int


class HorarioCreate(HorarioBase):
    pass


class HorarioUpdate(BaseModel):
    codigo_horario: Optional[str] = None  # NUEVO
    dia: Optional[str] = None
    hora_inicio: Optional[time] = None
    hora_final: Optional[time] = None
    aula_id: Optional[int] = None


class HorarioInDB(HorarioBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class Horario(HorarioInDB):
    pass


class HorarioWithRelations(Horario):
    aula: Optional["Aula"] = None
    grupos: Optional[List["Grupo"]] = []
