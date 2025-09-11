from sqlalchemy import Column, String, Integer, ForeignKey, Time
from sqlalchemy.orm import relationship
from .base import BaseModel


class Horario(BaseModel):
    __tablename__ = "horarios"

    dia = Column(String(20), nullable=False)
    hora_inicio = Column(Time, nullable=False)
    hora_final = Column(Time, nullable=False)
    aula_id = Column(Integer, ForeignKey("aulas.id"), nullable=False)

    # Relationships
    aula = relationship("Aula", back_populates="horarios")
    grupos = relationship("Grupo", back_populates="horario")
