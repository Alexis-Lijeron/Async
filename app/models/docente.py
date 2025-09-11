from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class Docente(BaseModel):
    __tablename__ = "docentes"

    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)

    # Relationships
    grupos = relationship("Grupo", back_populates="docente")
