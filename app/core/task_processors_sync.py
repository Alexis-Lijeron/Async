from typing import Dict, Any, Optional, Callable
from sqlalchemy.orm import Session

from app.config.database import SessionLocal
from app.models.task import Task


class RollbackManager:
    """Maneja operaciones de rollback síncronas"""

    @staticmethod
    def rollback_create_operation(table_name: str, record_id: int):
        """Rollback de operación CREATE - eliminar registro"""
        try:
            model_map = {
                "estudiantes": "app.models.estudiante.Estudiante",
                "docentes": "app.models.docente.Docente",
                "carreras": "app.models.carrera.Carrera",
                "materias": "app.models.materia.Materia",
                "grupos": "app.models.grupo.Grupo",
                "inscripciones": "app.models.inscripcion.Inscripcion",
                "notas": "app.models.nota.Nota",
                "horarios": "app.models.horario.Horario",
                "aulas": "app.models.aula.Aula",
                "gestiones": "app.models.gestion.Gestion",
            }

            if table_name not in model_map:
                raise ValueError(f"Tabla no soportada: {table_name}")

            module_path, class_name = model_map[table_name].rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            model_class = getattr(module, class_name)

            with SessionLocal() as db:
                record = (
                    db.query(model_class).filter(model_class.id == record_id).first()
                )

                if record:
                    db.delete(record)
                    db.commit()
                    print(
                        f"🔙 Rollback completado: Eliminado {table_name}.id={record_id}"
                    )
                    return True
                else:
                    print(f"⚠️ Registro no encontrado: {table_name}.id={record_id}")
                    return True

        except Exception as e:
            print(f"❌ Error en rollback: {e}")
            return False

    @staticmethod
    def rollback_update_operation(
        table_name: str, record_id: int, original_data: Dict[str, Any]
    ):
        """Rollback de operación UPDATE - restaurar datos originales"""
        try:
            model_map = {
                "estudiantes": "app.models.estudiante.Estudiante",
                "docentes": "app.models.docente.Docente",
                "carreras": "app.models.carrera.Carrera",
                "materias": "app.models.materia.Materia",
                "grupos": "app.models.grupo.Grupo",
                "inscripciones": "app.models.inscripcion.Inscripcion",
                "notas": "app.models.nota.Nota",
                "horarios": "app.models.horario.Horario",
                "aulas": "app.models.aula.Aula",
                "gestiones": "app.models.gestion.Gestion",
            }

            if table_name not in model_map:
                raise ValueError(f"Tabla no soportada: {table_name}")

            module_path, class_name = model_map[table_name].rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            model_class = getattr(module, class_name)

            with SessionLocal() as db:
                record = (
                    db.query(model_class).filter(model_class.id == record_id).first()
                )

                if record:
                    for field, value in original_data.items():
                        if hasattr(record, field):
                            setattr(record, field, value)

                    db.commit()
                    print(
                        f"🔙 Rollback completado: Restaurado {table_name}.id={record_id}"
                    )
                    return True
                else:
                    print(f"⚠️ Registro no encontrado: {table_name}.id={record_id}")
                    return False

        except Exception as e:
            print(f"❌ Error en rollback: {e}")
            return False


# ============================================================================
# PROCESADORES DE ESTUDIANTES
# ============================================================================
def process_create_estudiante_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de estudiante con rollback (SÍNCRONO)"""
    try:
        from app.crud.estudiante import estudiante
        from app.schemas.estudiante import EstudianteCreate

        with SessionLocal() as db:
            task.progress = 20.0
            db.commit()

            estudiante_data = EstudianteCreate(**task_data)

            task.progress = 50.0
            db.commit()

            new_estudiante = estudiante.create(db, obj_in=estudiante_data)

            # Configurar rollback
            task.set_rollback_data(
                {
                    "operation": "create",
                    "table": "estudiantes",
                    "record_id": new_estudiante.id,
                }
            )

            db.commit()

            return {
                "success": True,
                "estudiante_id": new_estudiante.id,
                "message": f"Estudiante {new_estudiante.registro} creado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_update_estudiante_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar actualización de estudiante con rollback (SÍNCRONO)"""
    try:
        from app.crud.estudiante import estudiante
        from app.schemas.estudiante import EstudianteUpdate

        with SessionLocal() as db:
            estudiante_id = task_data.pop("id")

            db_estudiante = estudiante.get(db, estudiante_id)
            if not db_estudiante:
                return {"success": False, "error": "Estudiante no encontrado"}

            # Guardar estado original
            original_data = {
                "nombre": db_estudiante.nombre,
                "apellido": db_estudiante.apellido,
                "ci": db_estudiante.ci,
                "carrera_id": db_estudiante.carrera_id,
            }

            task.progress = 30.0
            db.commit()

            update_data = EstudianteUpdate(**task_data)
            updated_estudiante = estudiante.update(
                db, db_obj=db_estudiante, obj_in=update_data
            )

            # Configurar rollback
            task.set_rollback_data(
                {
                    "operation": "update",
                    "table": "estudiantes",
                    "record_id": estudiante_id,
                    "original_data": original_data,
                }
            )

            db.commit()

            return {
                "success": True,
                "estudiante_id": updated_estudiante.id,
                "message": f"Estudiante {updated_estudiante.registro} actualizado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_delete_estudiante_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar eliminación de estudiante (SÍNCRONO)"""
    try:
        from app.crud.estudiante import estudiante

        with SessionLocal() as db:
            estudiante_id = task_data["id"]
            deleted_estudiante = estudiante.remove(db, id=estudiante_id)

            if not deleted_estudiante:
                return {"success": False, "error": "Estudiante no encontrado"}

            return {
                "success": True,
                "estudiante_id": estudiante_id,
                "message": f"Estudiante eliminado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# PROCESADORES DE DOCENTES
# ============================================================================
def process_create_docente_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de docente (SÍNCRONO)"""
    try:
        from app.crud.docente import docente
        from app.schemas.docente import DocenteCreate

        with SessionLocal() as db:
            docente_data = DocenteCreate(**task_data)
            new_docente = docente.create(db, obj_in=docente_data)

            task.set_rollback_data(
                {
                    "operation": "create",
                    "table": "docentes",
                    "record_id": new_docente.id,
                }
            )

            db.commit()

            return {
                "success": True,
                "docente_id": new_docente.id,
                "message": f"Docente {new_docente.nombre} {new_docente.apellido} creado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_update_docente_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar actualización de docente (SÍNCRONO)"""
    try:
        from app.crud.docente import docente
        from app.schemas.docente import DocenteUpdate

        with SessionLocal() as db:
            docente_id = task_data.pop("id")
            db_docente = docente.get(db, docente_id)

            if not db_docente:
                return {"success": False, "error": "Docente no encontrado"}

            original_data = {
                "nombre": db_docente.nombre,
                "apellido": db_docente.apellido,
            }

            update_data = DocenteUpdate(**task_data)
            updated_docente = docente.update(db, db_obj=db_docente, obj_in=update_data)

            task.set_rollback_data(
                {
                    "operation": "update",
                    "table": "docentes",
                    "record_id": docente_id,
                    "original_data": original_data,
                }
            )

            db.commit()

            return {
                "success": True,
                "docente_id": updated_docente.id,
                "message": f"Docente {updated_docente.nombre} {updated_docente.apellido} actualizado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_delete_docente_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar eliminación de docente (SÍNCRONO)"""
    try:
        from app.crud.docente import docente

        with SessionLocal() as db:
            docente_id = task_data["id"]
            deleted_docente = docente.remove(db, id=docente_id)

            if not deleted_docente:
                return {"success": False, "error": "Docente no encontrado"}

            return {
                "success": True,
                "docente_id": docente_id,
                "message": f"Docente eliminado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# PROCESADORES DE CARRERAS
# ============================================================================
def process_create_carrera_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de carrera (SÍNCRONO)"""
    try:
        from app.crud.carrera import carrera
        from app.schemas.carrera import CarreraCreate

        with SessionLocal() as db:
            carrera_data = CarreraCreate(**task_data)
            new_carrera = carrera.create(db, obj_in=carrera_data)

            task.set_rollback_data(
                {
                    "operation": "create",
                    "table": "carreras",
                    "record_id": new_carrera.id,
                }
            )

            db.commit()

            return {
                "success": True,
                "carrera_id": new_carrera.id,
                "message": f"Carrera {new_carrera.codigo} - {new_carrera.nombre} creada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_update_carrera_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar actualización de carrera (SÍNCRONO)"""
    try:
        from app.crud.carrera import carrera
        from app.schemas.carrera import CarreraUpdate

        with SessionLocal() as db:
            carrera_id = task_data.pop("id")
            db_carrera = carrera.get(db, carrera_id)

            if not db_carrera:
                return {"success": False, "error": "Carrera no encontrada"}

            original_data = {
                "codigo": db_carrera.codigo,
                "nombre": db_carrera.nombre,
            }

            update_data = CarreraUpdate(**task_data)
            updated_carrera = carrera.update(db, db_obj=db_carrera, obj_in=update_data)

            task.set_rollback_data(
                {
                    "operation": "update",
                    "table": "carreras",
                    "record_id": carrera_id,
                    "original_data": original_data,
                }
            )

            db.commit()

            return {
                "success": True,
                "carrera_id": updated_carrera.id,
                "message": f"Carrera {updated_carrera.codigo} actualizada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_delete_carrera_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar eliminación de carrera (SÍNCRONO)"""
    try:
        from app.crud.carrera import carrera

        with SessionLocal() as db:
            carrera_id = task_data["id"]
            deleted_carrera = carrera.remove(db, id=carrera_id)

            if not deleted_carrera:
                return {"success": False, "error": "Carrera no encontrada"}

            return {
                "success": True,
                "carrera_id": carrera_id,
                "message": f"Carrera eliminada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# PROCESADORES DE MATERIAS
# ============================================================================
def process_create_materia_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de materia (SÍNCRONO)"""
    try:
        from app.crud.materia import materia
        from app.schemas.materia import MateriaCreate

        with SessionLocal() as db:
            materia_data = MateriaCreate(**task_data)
            new_materia = materia.create(db, obj_in=materia_data)

            task.set_rollback_data(
                {
                    "operation": "create",
                    "table": "materias",
                    "record_id": new_materia.id,
                }
            )

            db.commit()

            return {
                "success": True,
                "materia_id": new_materia.id,
                "message": f"Materia {new_materia.sigla} - {new_materia.nombre} creada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_update_materia_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar actualización de materia (SÍNCRONO)"""
    try:
        from app.crud.materia import materia
        from app.schemas.materia import MateriaUpdate

        with SessionLocal() as db:
            materia_id = task_data.pop("id")
            db_materia = materia.get(db, materia_id)

            if not db_materia:
                return {"success": False, "error": "Materia no encontrada"}

            original_data = {
                "sigla": db_materia.sigla,
                "nombre": db_materia.nombre,
                "creditos": db_materia.creditos,
                "es_electiva": db_materia.es_electiva,
                "nivel_id": db_materia.nivel_id,
                "plan_estudio_id": db_materia.plan_estudio_id,
            }

            update_data = MateriaUpdate(**task_data)
            updated_materia = materia.update(db, db_obj=db_materia, obj_in=update_data)

            task.set_rollback_data(
                {
                    "operation": "update",
                    "table": "materias",
                    "record_id": materia_id,
                    "original_data": original_data,
                }
            )

            db.commit()

            return {
                "success": True,
                "materia_id": updated_materia.id,
                "message": f"Materia {updated_materia.sigla} actualizada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_delete_materia_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar eliminación de materia (SÍNCRONO)"""
    try:
        from app.crud.materia import materia

        with SessionLocal() as db:
            materia_id = task_data["id"]
            deleted_materia = materia.remove(db, id=materia_id)

            if not deleted_materia:
                return {"success": False, "error": "Materia no encontrada"}

            return {
                "success": True,
                "materia_id": materia_id,
                "message": f"Materia eliminada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# PROCESADORES GENÉRICOS PARA OTRAS ENTIDADES
# ============================================================================
def process_create_grupo_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar creación de grupo (SÍNCRONO)"""
    try:
        from app.models.grupo import Grupo

        with SessionLocal() as db:
            new_grupo = Grupo(**task_data)
            db.add(new_grupo)
            db.commit()
            db.refresh(new_grupo)

            return {
                "success": True,
                "grupo_id": new_grupo.id,
                "message": f"Grupo {new_grupo.descripcion} creado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_create_inscripcion_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de inscripción (SÍNCRONO)"""
    try:
        from app.models.inscripcion import Inscripcion

        with SessionLocal() as db:
            new_inscripcion = Inscripcion(**task_data)
            db.add(new_inscripcion)
            db.commit()
            db.refresh(new_inscripcion)

            return {
                "success": True,
                "inscripcion_id": new_inscripcion.id,
                "message": f"Inscripción creada para estudiante {new_inscripcion.estudiante_id}",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_create_horario_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de horario (SÍNCRONO)"""
    try:
        from app.models.horario import Horario
        from datetime import time

        with SessionLocal() as db:
            # Convertir strings de tiempo a objetos time si es necesario
            if isinstance(task_data["hora_inicio"], str):
                hour, minute = map(int, task_data["hora_inicio"].split(":"))
                task_data["hora_inicio"] = time(hour, minute)

            if isinstance(task_data["hora_final"], str):
                hour, minute = map(int, task_data["hora_final"].split(":"))
                task_data["hora_final"] = time(hour, minute)

            new_horario = Horario(**task_data)
            db.add(new_horario)
            db.commit()
            db.refresh(new_horario)

            return {
                "success": True,
                "horario_id": new_horario.id,
                "message": f"Horario {new_horario.dia} {new_horario.hora_inicio}-{new_horario.hora_final} creado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_create_aula_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar creación de aula (SÍNCRONO)"""
    try:
        from app.models.aula import Aula

        with SessionLocal() as db:
            new_aula = Aula(**task_data)
            db.add(new_aula)
            db.commit()
            db.refresh(new_aula)

            return {
                "success": True,
                "aula_id": new_aula.id,
                "message": f"Aula {new_aula.modulo}-{new_aula.aula} creada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_create_gestion_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de gestión (SÍNCRONO)"""
    try:
        from app.models.gestion import Gestion

        with SessionLocal() as db:
            new_gestion = Gestion(**task_data)
            db.add(new_gestion)
            db.commit()
            db.refresh(new_gestion)

            return {
                "success": True,
                "gestion_id": new_gestion.id,
                "message": f"Gestión SEM {new_gestion.semestre}/{new_gestion.año} creada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_create_nota_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar creación de nota (SÍNCRONO)"""
    try:
        from app.models.nota import Nota

        with SessionLocal() as db:
            new_nota = Nota(**task_data)
            db.add(new_nota)
            db.commit()
            db.refresh(new_nota)

            estado = "Aprobado" if new_nota.nota >= 61 else "Reprobado"

            return {
                "success": True,
                "nota_id": new_nota.id,
                "message": f"Nota {new_nota.nota} ({estado}) creada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# PROCESADORES DE ROLLBACK Y UTILIDADES
# ============================================================================
def process_rollback_operation(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar operación de rollback (SÍNCRONO)"""
    try:
        operation = task_data.get("operation")
        table = task_data.get("table")
        record_id = task_data.get("record_id")
        original_task_id = task_data.get("original_task_id")

        print(f"🔄 Ejecutando rollback para tarea: {original_task_id}")

        if operation == "create":
            success = RollbackManager.rollback_create_operation(table, record_id)
        elif operation == "update":
            original_data = task_data.get("original_data", {})
            success = RollbackManager.rollback_update_operation(
                table, record_id, original_data
            )
        else:
            return {"success": False, "error": f"Operación no soportada: {operation}"}

        if success:
            # Marcar tarea original como rollback completado
            with SessionLocal() as db:
                original_task = (
                    db.query(Task).filter(Task.task_id == original_task_id).first()
                )
                if original_task:
                    original_task.needs_rollback = False
                    db.commit()

            return {
                "success": True,
                "message": f"Rollback completado para {operation} en {table}.{record_id}",
            }
        else:
            return {"success": False, "error": "Rollback falló"}

    except Exception as e:
        return {"success": False, "error": f"Error en rollback: {str(e)}"}


def process_test_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesador de prueba (SÍNCRONO)"""
    import time

    # Simular trabajo
    time.sleep(1)

    return {"success": True, "message": "Tarea de prueba completada", "data": task_data}


# ============================================================================
# MAPEO DE TIPOS DE TAREA A PROCESADORES
# ============================================================================
TASK_PROCESSORS: Dict[str, Callable] = {
    # Estudiantes
    "create_estudiante": process_create_estudiante_task,
    "update_estudiante": process_update_estudiante_task,
    "delete_estudiante": process_delete_estudiante_task,
    # Docentes
    "create_docente": process_create_docente_task,
    "update_docente": process_update_docente_task,
    "delete_docente": process_delete_docente_task,
    # Carreras
    "create_carrera": process_create_carrera_task,
    "update_carrera": process_update_carrera_task,
    "delete_carrera": process_delete_carrera_task,
    # Materias
    "create_materia": process_create_materia_task,
    "update_materia": process_update_materia_task,
    "delete_materia": process_delete_materia_task,
    # Grupos
    "create_grupo": process_create_grupo_task,
    "update_grupo": process_create_grupo_task,  # Usar el mismo por simplicidad
    "delete_grupo": process_create_grupo_task,  # Implementar delete específico si es necesario
    # Inscripciones
    "create_inscripcion": process_create_inscripcion_task,
    "update_inscripcion": process_create_inscripcion_task,
    "delete_inscripcion": process_create_inscripcion_task,
    # Horarios
    "create_horario": process_create_horario_task,
    "update_horario": process_create_horario_task,
    "delete_horario": process_create_horario_task,
    # Aulas
    "create_aula": process_create_aula_task,
    "update_aula": process_create_aula_task,
    "delete_aula": process_create_aula_task,
    # Gestiones
    "create_gestion": process_create_gestion_task,
    "update_gestion": process_create_gestion_task,
    "delete_gestion": process_create_gestion_task,
    # Notas
    "create_nota": process_create_nota_task,
    "update_nota": process_create_nota_task,
    "delete_nota": process_create_nota_task,
    # Utilidades
    "rollback_operation": process_rollback_operation,
    "test_task": process_test_task,
}


def get_task_processor(task_type: str) -> Optional[Callable]:
    """Obtener procesador para un tipo de tarea"""
    return TASK_PROCESSORS.get(task_type)


def register_task_processor(task_type: str, processor: Callable):
    """Registrar nuevo procesador de tarea"""
    TASK_PROCESSORS[task_type] = processor
    print(f"📝 Procesador registrado: {task_type}")


def list_available_processors() -> List[str]:
    """Listar todos los procesadores disponibles"""
    return list(TASK_PROCESSORS.keys())
