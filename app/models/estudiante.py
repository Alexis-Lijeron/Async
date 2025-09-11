from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel


class Estudiante(BaseModel):
    __tablename__ = "estudiantes"

    registro = Column(String(20), unique=True, nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    ci = Column(String(20), unique=True, nullable=False)
    contraseña = Column(String(255), nullable=False)
    carrera_id = Column(Integer, ForeignKey("carreras.id"), nullable=False)

    # Relationships
    carrera = relationship("Carrera", back_populates="estudiantes")
    inscripciones = relationship("Inscripcion", back_populates="estudiante")
    notas = relationship("Nota", back_populates="estudiante")
