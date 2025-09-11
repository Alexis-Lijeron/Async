from sqlalchemy import Column, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel


class Nota(BaseModel):
    __tablename__ = "notas"

    nota = Column(Float, nullable=False)
    estudiante_id = Column(Integer, ForeignKey("estudiantes.id"), nullable=False)

    # Relationships
    estudiante = relationship("Estudiante", back_populates="notas")
