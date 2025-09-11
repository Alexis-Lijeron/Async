from fastapi import APIRouter

from app.api.v1 import estudiantes, docentes, carreras, materias, grupos, inscripciones

api_router = APIRouter()

api_router.include_router(
    estudiantes.router, prefix="/estudiantes", tags=["estudiantes"]
)
api_router.include_router(docentes.router, prefix="/docentes", tags=["docentes"])
api_router.include_router(carreras.router, prefix="/carreras", tags=["carreras"])
api_router.include_router(materias.router, prefix="/materias", tags=["materias"])
api_router.include_router(grupos.router, prefix="/grupos", tags=["grupos"])
api_router.include_router(
    inscripciones.router, prefix="/inscripciones", tags=["inscripciones"]
)
