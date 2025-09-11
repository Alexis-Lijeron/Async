from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel


class PlanEstudio(BaseModel):
    __tablename__ = "planes_estudio"

    codigo = Column(String(20), unique=True, nullable=False, index=True)
    cant_semestre = Column(Integer, nullable=False)
    plan = Column(String(100), nullable=False)
    carrera_id = Column(Integer, ForeignKey("carreras.id"), nullable=False)

    # Relationships
    carrera = relationship("Carrera", back_populates="planes_estudio")
    materias = relationship("Materia", back_populates="plan_estudio")
