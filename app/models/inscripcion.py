from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel


class Inscripcion(BaseModel):
    __tablename__ = "inscripciones"
    
    codigo_inscripcion = Column(String(30), unique=True, nullable=False, index=True)
    semestre = Column(Integer, nullable=False)
    gestion_id = Column(Integer, ForeignKey("gestiones.id"), nullable=False)
    estudiante_id = Column(Integer, ForeignKey("estudiantes.id"), nullable=False)
    grupo_id = Column(Integer, ForeignKey("grupos.id"), nullable=False)

    # Relationships
    gestion = relationship("Gestion", back_populates="inscripciones")
    estudiante = relationship("Estudiante", back_populates="inscripciones")
    grupo = relationship("Grupo", back_populates="inscripciones")
