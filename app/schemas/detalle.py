from pydantic import BaseModel, ConfigDict
from typing import Optional, TYPE_CHECKING
from datetime import datetime, date, time

if TYPE_CHECKING:
    from .grupo import Grupo


class DetalleBase(BaseModel):
    fecha: date
    hora: time
    grupo_id: int


class DetalleCreate(DetalleBase):
    pass


class DetalleUpdate(BaseModel):
    fecha: Optional[date] = None
    hora: Optional[time] = None
    grupo_id: Optional[int] = None


class DetalleInDB(DetalleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class Detalle(DetalleInDB):
    pass


class DetalleWithRelations(Detalle):
    grupo: Optional["Grupo"] = None
