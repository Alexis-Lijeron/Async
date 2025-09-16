from typing import Dict, Any, Optional, Callable, List
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
                "detalles": "app.models.detalle.Detalle",
                "prerrequisitos": "app.models.prerrequisito.Prerrequisito",
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
                "detalles": "app.models.detalle.Detalle",
                "prerrequisitos": "app.models.prerrequisito.Prerrequisito",
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
                "registro": new_estudiante.registro,
                "message": f"Estudiante {new_estudiante.registro} - {new_estudiante.nombre} {new_estudiante.apellido} creado",
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
                "registro": updated_estudiante.registro,
                "message": f"Estudiante {updated_estudiante.registro} - {updated_estudiante.nombre} {updated_estudiante.apellido} actualizado",
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
                "registro": deleted_estudiante.registro,
                "message": f"Estudiante {deleted_estudiante.registro} eliminado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# PROCESADORES DE DOCENTES CON CÓDIGO ÚNICO
# ============================================================================
def process_create_docente_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de docente con código único (SÍNCRONO)"""
    try:
        from app.models.docente import Docente

        with SessionLocal() as db:
            # Generar código único si no se proporciona
            if "codigo_docente" not in task_data:
                last_docente = (
                    db.query(Docente).order_by(Docente.codigo_docente.desc()).first()
                )
                if last_docente and last_docente.codigo_docente.startswith("DOC-"):
                    try:
                        last_num = int(last_docente.codigo_docente.split("-")[1])
                        new_num = last_num + 1
                    except:
                        new_num = 1
                else:
                    new_num = 1
                task_data["codigo_docente"] = f"DOC-{new_num:03d}"

            new_docente = Docente(**task_data)
            db.add(new_docente)
            db.commit()
            db.refresh(new_docente)

            task.set_rollback_data(
                {
                    "operation": "create",
                    "table": "docentes",
                    "record_id": new_docente.id,
                }
            )

            return {
                "success": True,
                "docente_id": new_docente.id,
                "codigo_docente": new_docente.codigo_docente,
                "message": f"Docente {new_docente.codigo_docente} - {new_docente.nombre} {new_docente.apellido} creado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_update_docente_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar actualización de docente (SÍNCRONO)"""
    try:
        from app.models.docente import Docente

        with SessionLocal() as db:
            docente_id = task_data.pop("id")
            db_docente = db.query(Docente).filter(Docente.id == docente_id).first()

            if not db_docente:
                return {"success": False, "error": "Docente no encontrado"}

            original_data = {
                "codigo_docente": db_docente.codigo_docente,
                "nombre": db_docente.nombre,
                "apellido": db_docente.apellido,
            }

            for field, value in task_data.items():
                if hasattr(db_docente, field):
                    setattr(db_docente, field, value)

            db.commit()

            task.set_rollback_data(
                {
                    "operation": "update",
                    "table": "docentes",
                    "record_id": docente_id,
                    "original_data": original_data,
                }
            )

            return {
                "success": True,
                "docente_id": db_docente.id,
                "codigo_docente": db_docente.codigo_docente,
                "message": f"Docente {db_docente.codigo_docente} - {db_docente.nombre} {db_docente.apellido} actualizado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_delete_docente_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar eliminación de docente (SÍNCRONO)"""
    try:
        from app.models.docente import Docente

        with SessionLocal() as db:
            docente_id = task_data["id"]
            docente = db.query(Docente).filter(Docente.id == docente_id).first()

            if not docente:
                return {"success": False, "error": "Docente no encontrado"}

            codigo_docente = docente.codigo_docente
            db.delete(docente)
            db.commit()

            return {
                "success": True,
                "docente_id": docente_id,
                "codigo_docente": codigo_docente,
                "message": f"Docente {codigo_docente} eliminado",
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
                "codigo": new_carrera.codigo,
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
                "codigo": updated_carrera.codigo,
                "message": f"Carrera {updated_carrera.codigo} - {updated_carrera.nombre} actualizada",
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
                "codigo": deleted_carrera.codigo,
                "message": f"Carrera {deleted_carrera.codigo} eliminada",
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
                "sigla": new_materia.sigla,
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
                "sigla": updated_materia.sigla,
                "message": f"Materia {updated_materia.sigla} - {updated_materia.nombre} actualizada",
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
                "sigla": deleted_materia.sigla,
                "message": f"Materia {deleted_materia.sigla} eliminada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# PROCESADORES GENÉRICOS PARA OTRAS ENTIDADES CON CÓDIGOS ÚNICOS
# ============================================================================
def process_create_grupo_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar creación de grupo con código único (SÍNCRONO)"""
    try:
        from app.models.grupo import Grupo
        from app.models.materia import Materia
        from app.models.gestion import Gestion

        with SessionLocal() as db:
            # Generar código único si no se proporciona
            if "codigo_grupo" not in task_data:
                materia = (
                    db.query(Materia)
                    .filter(Materia.id == task_data["materia_id"])
                    .first()
                )
                gestion = (
                    db.query(Gestion)
                    .filter(Gestion.id == task_data["gestion_id"])
                    .first()
                )

                if materia and gestion:
                    existing_count = (
                        db.query(Grupo)
                        .filter(
                            Grupo.materia_id == task_data["materia_id"],
                            Grupo.gestion_id == task_data["gestion_id"],
                        )
                        .count()
                    )

                    task_data["codigo_grupo"] = (
                        f"GRP-{materia.sigla}-{gestion.año}-{gestion.semestre}-{existing_count + 1:02d}"
                    )

            new_grupo = Grupo(**task_data)
            db.add(new_grupo)
            db.commit()
            db.refresh(new_grupo)

            return {
                "success": True,
                "grupo_id": new_grupo.id,
                "codigo_grupo": new_grupo.codigo_grupo,
                "message": f"Grupo {new_grupo.codigo_grupo} creado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_create_inscripcion_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de inscripción con código único (SÍNCRONO)"""
    try:
        from app.models.inscripcion import Inscripcion
        from app.models.estudiante import Estudiante
        from app.models.grupo import Grupo
        from app.models.gestion import Gestion
        from app.models.materia import Materia

        with SessionLocal() as db:
            # Generar código único si no se proporciona
            if "codigo_inscripcion" not in task_data:
                estudiante = (
                    db.query(Estudiante)
                    .filter(Estudiante.id == task_data["estudiante_id"])
                    .first()
                )
                grupo = (
                    db.query(Grupo).filter(Grupo.id == task_data["grupo_id"]).first()
                )
                gestion = (
                    db.query(Gestion)
                    .filter(Gestion.id == task_data["gestion_id"])
                    .first()
                )

                if estudiante and grupo and gestion:
                    materia = (
                        db.query(Materia).filter(Materia.id == grupo.materia_id).first()
                    )
                    if materia:
                        task_data["codigo_inscripcion"] = (
                            f"INS-{estudiante.registro}-{materia.sigla}-{gestion.año}-{gestion.semestre}"
                        )

            new_inscripcion = Inscripcion(**task_data)
            db.add(new_inscripcion)
            db.commit()
            db.refresh(new_inscripcion)

            return {
                "success": True,
                "inscripcion_id": new_inscripcion.id,
                "codigo_inscripcion": new_inscripcion.codigo_inscripcion,
                "message": f"Inscripción {new_inscripcion.codigo_inscripcion} creada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_create_horario_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de horario con código único (SÍNCRONO)"""
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

            # Generar código único si no se proporciona
            if "codigo_horario" not in task_data:
                dia = task_data.get("dia", "")
                hora_inicio = task_data["hora_inicio"]
                hora_final = task_data["hora_final"]
                task_data["codigo_horario"] = (
                    f"HOR-{dia[:3].upper()}-{hora_inicio.strftime('%H%M')}-{hora_final.strftime('%H%M')}"
                )

            new_horario = Horario(**task_data)
            db.add(new_horario)
            db.commit()
            db.refresh(new_horario)

            return {
                "success": True,
                "horario_id": new_horario.id,
                "codigo_horario": new_horario.codigo_horario,
                "message": f"Horario {new_horario.codigo_horario} creado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_create_aula_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar creación de aula con código único (SÍNCRONO)"""
    try:
        from app.models.aula import Aula

        with SessionLocal() as db:
            # Generar código único si no se proporciona
            if "codigo_aula" not in task_data:
                modulo = task_data.get("modulo", "")
                aula = task_data.get("aula", "")
                task_data["codigo_aula"] = f"AULA-{modulo}-{aula}"

            new_aula = Aula(**task_data)
            db.add(new_aula)
            db.commit()
            db.refresh(new_aula)

            return {
                "success": True,
                "aula_id": new_aula.id,
                "codigo_aula": new_aula.codigo_aula,
                "message": f"Aula {new_aula.codigo_aula} creada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_create_gestion_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de gestión con código único (SÍNCRONO)"""
    try:
        from app.models.gestion import Gestion

        with SessionLocal() as db:
            # Generar código único si no se proporciona
            if "codigo_gestion" not in task_data:
                semestre = task_data.get("semestre")
                año = task_data.get("año")
                task_data["codigo_gestion"] = f"GEST-{año}-{semestre}"

            new_gestion = Gestion(**task_data)
            db.add(new_gestion)
            db.commit()
            db.refresh(new_gestion)

            return {
                "success": True,
                "gestion_id": new_gestion.id,
                "codigo_gestion": new_gestion.codigo_gestion,
                "message": f"Gestión {new_gestion.codigo_gestion} creada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_create_nota_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar creación de nota con código único (SÍNCRONO)"""
    try:
        from app.models.nota import Nota
        from app.models.estudiante import Estudiante

        with SessionLocal() as db:
            # Generar código único si no se proporciona
            if "codigo_nota" not in task_data:
                estudiante = (
                    db.query(Estudiante)
                    .filter(Estudiante.id == task_data["estudiante_id"])
                    .first()
                )

                if estudiante:
                    existing_count = (
                        db.query(Nota)
                        .filter(Nota.estudiante_id == task_data["estudiante_id"])
                        .count()
                    )
                    task_data["codigo_nota"] = (
                        f"NOTA-{estudiante.registro}-{existing_count + 1:03d}"
                    )

            new_nota = Nota(**task_data)
            db.add(new_nota)
            db.commit()
            db.refresh(new_nota)

            estado = "Aprobado" if new_nota.nota >= 61 else "Reprobado"

            return {
                "success": True,
                "nota_id": new_nota.id,
                "codigo_nota": new_nota.codigo_nota,
                "message": f"Nota {new_nota.codigo_nota}: {new_nota.nota} ({estado}) creada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_create_detalle_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de detalle con código único (SÍNCRONO)"""
    try:
        from app.models.detalle import Detalle
        from app.models.grupo import Grupo
        from app.models.materia import Materia

        with SessionLocal() as db:
            # Generar código único si no se proporciona
            if "codigo_detalle" not in task_data:
                grupo = (
                    db.query(Grupo).filter(Grupo.id == task_data["grupo_id"]).first()
                )

                if grupo:
                    materia = (
                        db.query(Materia).filter(Materia.id == grupo.materia_id).first()
                    )
                    if materia:
                        fecha = task_data.get("fecha")
                        if isinstance(fecha, str):
                            from datetime import datetime

                            fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
                        else:
                            fecha_obj = fecha

                        existing_count = (
                            db.query(Detalle)
                            .filter(
                                Detalle.grupo_id == task_data["grupo_id"],
                                Detalle.fecha == fecha_obj,
                            )
                            .count()
                        )

                        task_data["codigo_detalle"] = (
                            f"DET-{materia.sigla}-{fecha_obj.strftime('%Y%m%d')}-{existing_count + 1:02d}"
                        )

            new_detalle = Detalle(**task_data)
            db.add(new_detalle)
            db.commit()
            db.refresh(new_detalle)

            return {
                "success": True,
                "detalle_id": new_detalle.id,
                "codigo_detalle": new_detalle.codigo_detalle,
                "message": f"Detalle {new_detalle.codigo_detalle} creado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_create_prerrequisito_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar creación de prerrequisito con código único (SÍNCRONO)"""
    try:
        from app.models.prerrequisito import Prerrequisito

        with SessionLocal() as db:
            # Generar código único si no se proporciona
            if "codigo_prerrequisito" not in task_data:
                existing_count = db.query(Prerrequisito).count()
                task_data["codigo_prerrequisito"] = f"PREREQ-{existing_count + 1:03d}"

            new_prerrequisito = Prerrequisito(**task_data)
            db.add(new_prerrequisito)
            db.commit()
            db.refresh(new_prerrequisito)

            return {
                "success": True,
                "prerrequisito_id": new_prerrequisito.id,
                "codigo_prerrequisito": new_prerrequisito.codigo_prerrequisito,
                "message": f"Prerrequisito {new_prerrequisito.codigo_prerrequisito} creado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# PROCESADORES DE UPDATE Y DELETE GENÉRICOS
# ============================================================================
def process_update_grupo_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar actualización de grupo (SÍNCRONO)"""
    try:
        from app.models.grupo import Grupo

        with SessionLocal() as db:
            grupo_id = task_data.pop("id")
            grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()

            if not grupo:
                return {"success": False, "error": "Grupo no encontrado"}

            for field, value in task_data.items():
                if hasattr(grupo, field):
                    setattr(grupo, field, value)

            db.commit()

            return {
                "success": True,
                "grupo_id": grupo.id,
                "codigo_grupo": grupo.codigo_grupo,
                "message": f"Grupo {grupo.codigo_grupo} actualizado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_update_inscripcion_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar actualización de inscripción (SÍNCRONO)"""
    try:
        from app.models.inscripcion import Inscripcion

        with SessionLocal() as db:
            inscripcion_id = task_data.pop("id")
            inscripcion = (
                db.query(Inscripcion).filter(Inscripcion.id == inscripcion_id).first()
            )

            if not inscripcion:
                return {"success": False, "error": "Inscripción no encontrada"}

            for field, value in task_data.items():
                if hasattr(inscripcion, field):
                    setattr(inscripcion, field, value)

            db.commit()

            return {
                "success": True,
                "inscripcion_id": inscripcion.id,
                "codigo_inscripcion": inscripcion.codigo_inscripcion,
                "message": f"Inscripción {inscripcion.codigo_inscripcion} actualizada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_update_horario_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar actualización de horario (SÍNCRONO)"""
    try:
        from app.models.horario import Horario
        from datetime import time

        with SessionLocal() as db:
            horario_id = task_data.pop("id")
            horario = db.query(Horario).filter(Horario.id == horario_id).first()

            if not horario:
                return {"success": False, "error": "Horario no encontrado"}

            # Convertir strings de tiempo si es necesario
            if "hora_inicio" in task_data and isinstance(task_data["hora_inicio"], str):
                hour, minute = map(int, task_data["hora_inicio"].split(":"))
                task_data["hora_inicio"] = time(hour, minute)

            if "hora_final" in task_data and isinstance(task_data["hora_final"], str):
                hour, minute = map(int, task_data["hora_final"].split(":"))
                task_data["hora_final"] = time(hour, minute)

            for field, value in task_data.items():
                if hasattr(horario, field):
                    setattr(horario, field, value)

            # Regenerar código si cambiaron los datos relevantes
            if any(
                field in task_data for field in ["dia", "hora_inicio", "hora_final"]
            ):
                horario.codigo_horario = f"HOR-{horario.dia[:3].upper()}-{horario.hora_inicio.strftime('%H%M')}-{horario.hora_final.strftime('%H%M')}"

            db.commit()

            return {
                "success": True,
                "horario_id": horario.id,
                "codigo_horario": horario.codigo_horario,
                "message": f"Horario {horario.codigo_horario} actualizado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_update_aula_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar actualización de aula (SÍNCRONO)"""
    try:
        from app.models.aula import Aula

        with SessionLocal() as db:
            aula_id = task_data.pop("id")
            aula = db.query(Aula).filter(Aula.id == aula_id).first()

            if not aula:
                return {"success": False, "error": "Aula no encontrada"}

            for field, value in task_data.items():
                if hasattr(aula, field):
                    setattr(aula, field, value)

            # Regenerar código si cambiaron módulo o aula
            if "modulo" in task_data or "aula" in task_data:
                aula.codigo_aula = f"AULA-{aula.modulo}-{aula.aula}"

            db.commit()

            return {
                "success": True,
                "aula_id": aula.id,
                "codigo_aula": aula.codigo_aula,
                "message": f"Aula {aula.codigo_aula} actualizada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_update_gestion_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar actualización de gestión (SÍNCRONO)"""
    try:
        from app.models.gestion import Gestion

        with SessionLocal() as db:
            gestion_id = task_data.pop("id")
            gestion = db.query(Gestion).filter(Gestion.id == gestion_id).first()

            if not gestion:
                return {"success": False, "error": "Gestión no encontrada"}

            for field, value in task_data.items():
                if hasattr(gestion, field):
                    setattr(gestion, field, value)

            # Regenerar código si cambiaron semestre o año
            if "semestre" in task_data or "año" in task_data:
                gestion.codigo_gestion = f"GEST-{gestion.año}-{gestion.semestre}"

            db.commit()

            return {
                "success": True,
                "gestion_id": gestion.id,
                "codigo_gestion": gestion.codigo_gestion,
                "message": f"Gestión {gestion.codigo_gestion} actualizada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_update_nota_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar actualización de nota (SÍNCRONO)"""
    try:
        from app.models.nota import Nota

        with SessionLocal() as db:
            nota_id = task_data.pop("id")
            nota = db.query(Nota).filter(Nota.id == nota_id).first()

            if not nota:
                return {"success": False, "error": "Nota no encontrada"}

            for field, value in task_data.items():
                if hasattr(nota, field):
                    setattr(nota, field, value)

            db.commit()

            estado = "Aprobado" if nota.nota >= 61 else "Reprobado"

            return {
                "success": True,
                "nota_id": nota.id,
                "codigo_nota": nota.codigo_nota,
                "message": f"Nota {nota.codigo_nota}: {nota.nota} ({estado}) actualizada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_update_detalle_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar actualización de detalle (SÍNCRONO)"""
    try:
        from app.models.detalle import Detalle

        with SessionLocal() as db:
            detalle_id = task_data.pop("id")
            detalle = db.query(Detalle).filter(Detalle.id == detalle_id).first()

            if not detalle:
                return {"success": False, "error": "Detalle no encontrado"}

            for field, value in task_data.items():
                if hasattr(detalle, field):
                    setattr(detalle, field, value)

            db.commit()

            return {
                "success": True,
                "detalle_id": detalle.id,
                "codigo_detalle": detalle.codigo_detalle,
                "message": f"Detalle {detalle.codigo_detalle} actualizado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_update_prerrequisito_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar actualización de prerrequisito (SÍNCRONO)"""
    try:
        from app.models.prerrequisito import Prerrequisito

        with SessionLocal() as db:
            prerrequisito_id = task_data.pop("id")
            prerrequisito = (
                db.query(Prerrequisito)
                .filter(Prerrequisito.id == prerrequisito_id)
                .first()
            )

            if not prerrequisito:
                return {"success": False, "error": "Prerrequisito no encontrado"}

            for field, value in task_data.items():
                if hasattr(prerrequisito, field):
                    setattr(prerrequisito, field, value)

            db.commit()

            return {
                "success": True,
                "prerrequisito_id": prerrequisito.id,
                "codigo_prerrequisito": prerrequisito.codigo_prerrequisito,
                "message": f"Prerrequisito {prerrequisito.codigo_prerrequisito} actualizado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# PROCESADORES DE DELETE GENÉRICOS
# ============================================================================
def process_delete_grupo_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar eliminación de grupo (SÍNCRONO)"""
    try:
        from app.models.grupo import Grupo

        with SessionLocal() as db:
            grupo_id = task_data["id"]
            grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()

            if not grupo:
                return {"success": False, "error": "Grupo no encontrado"}

            codigo_grupo = grupo.codigo_grupo
            db.delete(grupo)
            db.commit()

            return {
                "success": True,
                "grupo_id": grupo_id,
                "codigo_grupo": codigo_grupo,
                "message": f"Grupo {codigo_grupo} eliminado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_delete_inscripcion_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar eliminación de inscripción (SÍNCRONO)"""
    try:
        from app.models.inscripcion import Inscripcion

        with SessionLocal() as db:
            inscripcion_id = task_data["id"]
            inscripcion = (
                db.query(Inscripcion).filter(Inscripcion.id == inscripcion_id).first()
            )

            if not inscripcion:
                return {"success": False, "error": "Inscripción no encontrada"}

            codigo_inscripcion = inscripcion.codigo_inscripcion
            db.delete(inscripcion)
            db.commit()

            return {
                "success": True,
                "inscripcion_id": inscripcion_id,
                "codigo_inscripcion": codigo_inscripcion,
                "message": f"Inscripción {codigo_inscripcion} eliminada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_delete_horario_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar eliminación de horario (SÍNCRONO)"""
    try:
        from app.models.horario import Horario

        with SessionLocal() as db:
            horario_id = task_data["id"]
            horario = db.query(Horario).filter(Horario.id == horario_id).first()

            if not horario:
                return {"success": False, "error": "Horario no encontrado"}

            codigo_horario = horario.codigo_horario
            db.delete(horario)
            db.commit()

            return {
                "success": True,
                "horario_id": horario_id,
                "codigo_horario": codigo_horario,
                "message": f"Horario {codigo_horario} eliminado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_delete_aula_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar eliminación de aula (SÍNCRONO)"""
    try:
        from app.models.aula import Aula

        with SessionLocal() as db:
            aula_id = task_data["id"]
            aula = db.query(Aula).filter(Aula.id == aula_id).first()

            if not aula:
                return {"success": False, "error": "Aula no encontrada"}

            codigo_aula = aula.codigo_aula
            db.delete(aula)
            db.commit()

            return {
                "success": True,
                "aula_id": aula_id,
                "codigo_aula": codigo_aula,
                "message": f"Aula {codigo_aula} eliminada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_delete_gestion_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar eliminación de gestión (SÍNCRONO)"""
    try:
        from app.models.gestion import Gestion

        with SessionLocal() as db:
            gestion_id = task_data["id"]
            gestion = db.query(Gestion).filter(Gestion.id == gestion_id).first()

            if not gestion:
                return {"success": False, "error": "Gestión no encontrada"}

            codigo_gestion = gestion.codigo_gestion
            db.delete(gestion)
            db.commit()

            return {
                "success": True,
                "gestion_id": gestion_id,
                "codigo_gestion": codigo_gestion,
                "message": f"Gestión {codigo_gestion} eliminada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_delete_nota_task(task_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
    """Procesar eliminación de nota (SÍNCRONO)"""
    try:
        from app.models.nota import Nota

        with SessionLocal() as db:
            nota_id = task_data["id"]
            nota = db.query(Nota).filter(Nota.id == nota_id).first()

            if not nota:
                return {"success": False, "error": "Nota no encontrada"}

            codigo_nota = nota.codigo_nota
            db.delete(nota)
            db.commit()

            return {
                "success": True,
                "nota_id": nota_id,
                "codigo_nota": codigo_nota,
                "message": f"Nota {codigo_nota} eliminada",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_delete_detalle_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar eliminación de detalle (SÍNCRONO)"""
    try:
        from app.models.detalle import Detalle

        with SessionLocal() as db:
            detalle_id = task_data["id"]
            detalle = db.query(Detalle).filter(Detalle.id == detalle_id).first()

            if not detalle:
                return {"success": False, "error": "Detalle no encontrado"}

            codigo_detalle = detalle.codigo_detalle
            db.delete(detalle)
            db.commit()

            return {
                "success": True,
                "detalle_id": detalle_id,
                "codigo_detalle": codigo_detalle,
                "message": f"Detalle {codigo_detalle} eliminado",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_delete_prerrequisito_task(
    task_data: Dict[str, Any], task: Task
) -> Dict[str, Any]:
    """Procesar eliminación de prerrequisito (SÍNCRONO)"""
    try:
        from app.models.prerrequisito import Prerrequisito

        with SessionLocal() as db:
            prerrequisito_id = task_data["id"]
            prerrequisito = (
                db.query(Prerrequisito)
                .filter(Prerrequisito.id == prerrequisito_id)
                .first()
            )

            if not prerrequisito:
                return {"success": False, "error": "Prerrequisito no encontrado"}

            codigo_prerrequisito = prerrequisito.codigo_prerrequisito
            db.delete(prerrequisito)
            db.commit()

            return {
                "success": True,
                "prerrequisito_id": prerrequisito_id,
                "codigo_prerrequisito": codigo_prerrequisito,
                "message": f"Prerrequisito {codigo_prerrequisito} eliminado",
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
    "update_grupo": process_update_grupo_task,
    "delete_grupo": process_delete_grupo_task,
    # Inscripciones
    "create_inscripcion": process_create_inscripcion_task,
    "update_inscripcion": process_update_inscripcion_task,
    "delete_inscripcion": process_delete_inscripcion_task,
    # Horarios
    "create_horario": process_create_horario_task,
    "update_horario": process_update_horario_task,
    "delete_horario": process_delete_horario_task,
    # Aulas
    "create_aula": process_create_aula_task,
    "update_aula": process_update_aula_task,
    "delete_aula": process_delete_aula_task,
    # Gestiones
    "create_gestion": process_create_gestion_task,
    "update_gestion": process_update_gestion_task,
    "delete_gestion": process_delete_gestion_task,
    # Notas
    "create_nota": process_create_nota_task,
    "update_nota": process_update_nota_task,
    "delete_nota": process_delete_nota_task,
    # Detalles
    "create_detalle": process_create_detalle_task,
    "update_detalle": process_update_detalle_task,
    "delete_detalle": process_delete_detalle_task,
    # Prerrequisitos
    "create_prerrequisito": process_create_prerrequisito_task,
    "update_prerrequisito": process_update_prerrequisito_task,
    "delete_prerrequisito": process_delete_prerrequisito_task,
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
