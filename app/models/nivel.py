from sqlalchemy import Column, Integer
from sqlalchemy.orm import relationship
from .base import BaseModel


class Nivel(BaseModel):
    __tablename__ = "niveles"

    nivel = Column(Integer, nullable=False, unique=True)

    # Relationships
    materias = relationship("Materia", back_populates="nivel")
