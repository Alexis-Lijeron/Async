from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class Carrera(BaseModel):
    __tablename__ = "carreras"

    codigo = Column(String(10), unique=True, nullable=False, index=True)  
    nombre = Column(String(200), nullable=False)

    # Relationships
    estudiantes = relationship("Estudiante", back_populates="carrera")
    planes_estudio = relationship("PlanEstudio", back_populates="carrera")
