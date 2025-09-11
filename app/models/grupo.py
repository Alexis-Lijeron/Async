from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel


class Grupo(BaseModel):
    __tablename__ = "grupos"

    descripcion = Column(String(100), nullable=False)
    docente_id = Column(Integer, ForeignKey("docentes.id"), nullable=False)
    gestion_id = Column(Integer, ForeignKey("gestiones.id"), nullable=False)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False)
    horario_id = Column(Integer, ForeignKey("horarios.id"), nullable=False)

    # Relationships
    docente = relationship("Docente", back_populates="grupos")
    gestion = relationship("Gestion", back_populates="grupos")
    materia = relationship("Materia", back_populates="grupos")
    horario = relationship("Horario", back_populates="grupos")
    inscripciones = relationship("Inscripcion", back_populates="grupo")
    detalles = relationship("Detalle", back_populates="grupo")
