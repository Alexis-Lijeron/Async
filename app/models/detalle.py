from sqlalchemy import Column, Date, Time, Integer, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel


class Detalle(BaseModel):
    __tablename__ = "detalles"

    fecha = Column(Date, nullable=False)
    hora = Column(Time, nullable=False)
    grupo_id = Column(Integer, ForeignKey("grupos.id"), nullable=False)

    # Relationships
    grupo = relationship("Grupo", back_populates="detalles")
