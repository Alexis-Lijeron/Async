from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel


class Prerrequisito(BaseModel):
    __tablename__ = "prerrequisitos"

    codigo_prerrequisito = Column(String(30), unique=True, nullable=False, index=True)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False)
    sigla_prerrequisito = Column(String(20), nullable=False)

    # Solo una relación simple con la materia principal
    materia = relationship(
        "Materia",
        foreign_keys=[materia_id],
        back_populates="prerrequisitos_como_materia",
    )
