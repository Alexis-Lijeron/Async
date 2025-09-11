from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship
from .base import BaseModel


class Aula(BaseModel):
    __tablename__ = "aulas"

    modulo = Column(String(10), nullable=False)
    aula = Column(String(20), nullable=False)

    # Relationships
    horarios = relationship("Horario", back_populates="aula")
