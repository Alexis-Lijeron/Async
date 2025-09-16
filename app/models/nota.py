from sqlalchemy import Column, Float, Integer, ForeignKey, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class Nota(BaseModel):
    __tablename__ = "notas"

    codigo_nota = Column(String(30), unique=True, nullable=False, index=True)
    nota = Column(Float, nullable=False)
    estudiante_id = Column(Integer, ForeignKey("estudiantes.id"), nullable=False)

    # Relationships
    estudiante = relationship("Estudiante", back_populates="notas")
