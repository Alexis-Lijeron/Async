from .base import BaseModel
from .docente import Docente
from .estudiante import Estudiante
from .gestion import Gestion
from .grupo import Grupo
from .horario import Horario
from .aula import Aula
from .materia import Materia
from .nivel import Nivel
from .plan_estudio import PlanEstudio
from .carrera import Carrera
from .prerrequisito import Prerrequisito
from .inscripcion import Inscripcion
from .nota import Nota
from .detalle import Detalle

# Nuevos modelos para sistema de colas y paginación
from .task import Task
from .pagination_state import PaginationState

__all__ = [
    "BaseModel",
    "Docente",
    "Estudiante",
    "Gestion",
    "Grupo",
    "Horario",
    "Aula",
    "Materia",
    "Nivel",
    "PlanEstudio",
    "Carrera",
    "Prerrequisito",
    "Inscripcion",
    "Nota",
    "Detalle",
    # Nuevos modelos
    "Task",
    "PaginationState",
]
