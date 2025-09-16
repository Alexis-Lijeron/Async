from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class Gestion(BaseModel):
    __tablename__ = "gestiones"

    codigo_gestion = Column(String(20), unique=True, nullable=False, index=True)
    semestre = Column(Integer, nullable=False)
    año = Column(Integer, nullable=False)

    # Relationships
    grupos = relationship("Grupo", back_populates="gestion")
    inscripciones = relationship("Inscripcion", back_populates="gestion")
