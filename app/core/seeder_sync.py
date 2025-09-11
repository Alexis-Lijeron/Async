import time
from datetime import time as dt_time, date
from sqlalchemy.orm import Session

from app.config.database import SessionLocal
from app.core.security import get_password_hash
from app.models.carrera import Carrera
from app.models.plan_estudio import PlanEstudio
from app.models.nivel import Nivel
from app.models.materia import Materia
from app.models.prerrequisito import Prerrequisito
from app.models.docente import Docente
from app.models.estudiante import Estudiante
from app.models.aula import Aula
from app.models.horario import Horario
from app.models.gestion import Gestion
from app.models.grupo import Grupo
from app.models.inscripcion import Inscripcion
from app.models.nota import Nota
from app.models.detalle import Detalle


def seed_database():
    """Poblar la base de datos con datos iniciales"""

    with SessionLocal() as db:
        try:
            print("🌱 Iniciando seeding de la base de datos...")

            # 1. Crear Carrera
            print("🎓 Creando carrera...")
            carrera = Carrera(codigo="INF187", nombre="Ingeniería Informática")
            db.add(carrera)
            db.commit()
            db.refresh(carrera)

            # 2. Crear Plan de Estudios
            print("📚 Creando plan de estudios...")
            plan_estudio = PlanEstudio(
                codigo="INF187", cant_semestre=10, plan="187-3", carrera_id=carrera.id
            )
            db.add(plan_estudio)
            db.commit()
            db.refresh(plan_estudio)

            # 3. Crear Niveles (1-10 semestres)
            print("📊 Creando niveles...")
            niveles = []
            for i in range(1, 11):
                nivel = Nivel(nivel=i)
                db.add(nivel)
                niveles.append(nivel)
            db.commit()

            # Refresh niveles para obtener IDs
            for nivel in niveles:
                db.refresh(nivel)

            # 4. Crear Materias por semestre
            print("📖 Creando materias...")
            materias_data = [
                # SEM 1
                {"sigla": "MAT101", "nombre": "Cálculo I", "creditos": 5, "nivel": 1},
                {
                    "sigla": "INF119",
                    "nombre": "Estructuras Discretas",
                    "creditos": 4,
                    "nivel": 1,
                },
                {
                    "sigla": "INF110",
                    "nombre": "Introducción a la Informática",
                    "creditos": 3,
                    "nivel": 1,
                },
                {"sigla": "FIS100", "nombre": "Física I", "creditos": 4, "nivel": 1},
                {
                    "sigla": "LIN100",
                    "nombre": "Inglés Técnico I",
                    "creditos": 2,
                    "nivel": 1,
                },
                # SEM 2
                {"sigla": "MAT102", "nombre": "Cálculo II", "creditos": 5, "nivel": 2},
                {
                    "sigla": "MAT103",
                    "nombre": "Álgebra Lineal",
                    "creditos": 4,
                    "nivel": 2,
                },
                {
                    "sigla": "INF120",
                    "nombre": "Programación I",
                    "creditos": 4,
                    "nivel": 2,
                },
                {"sigla": "FIS102", "nombre": "Física II", "creditos": 4, "nivel": 2},
                {
                    "sigla": "LIN101",
                    "nombre": "Inglés Técnico II",
                    "creditos": 2,
                    "nivel": 2,
                },
                # SEM 3
                {
                    "sigla": "MAT207",
                    "nombre": "Ecuaciones Diferenciales",
                    "creditos": 4,
                    "nivel": 3,
                },
                {
                    "sigla": "INF210",
                    "nombre": "Programación II",
                    "creditos": 4,
                    "nivel": 3,
                },
                {
                    "sigla": "INF211",
                    "nombre": "Arquitectura de Computadoras",
                    "creditos": 4,
                    "nivel": 3,
                },
                {"sigla": "FIS200", "nombre": "Física III", "creditos": 4, "nivel": 3},
                {
                    "sigla": "ADM100",
                    "nombre": "Administración",
                    "creditos": 3,
                    "nivel": 3,
                },
                # SEM 4
                {
                    "sigla": "MAT202",
                    "nombre": "Probabilidades y Estadísticas I",
                    "creditos": 4,
                    "nivel": 4,
                },
                {
                    "sigla": "INF205",
                    "nombre": "Métodos Numéricos",
                    "creditos": 4,
                    "nivel": 4,
                },
                {
                    "sigla": "INF220",
                    "nombre": "Estructura de Datos I",
                    "creditos": 4,
                    "nivel": 4,
                },
                {
                    "sigla": "INF221",
                    "nombre": "Programación Ensamblador",
                    "creditos": 4,
                    "nivel": 4,
                },
                {
                    "sigla": "ADM200",
                    "nombre": "Contabilidad",
                    "creditos": 3,
                    "nivel": 4,
                },
                # SEM 5
                {
                    "sigla": "MAT302",
                    "nombre": "Probabilidades y Estadísticas II",
                    "creditos": 4,
                    "nivel": 5,
                },
                {
                    "sigla": "INF318",
                    "nombre": "Programación Lógica y Funcional",
                    "creditos": 4,
                    "nivel": 5,
                },
                {
                    "sigla": "INF310",
                    "nombre": "Estructura de Datos II",
                    "creditos": 4,
                    "nivel": 5,
                },
                {
                    "sigla": "INF312",
                    "nombre": "Base de Datos I",
                    "creditos": 4,
                    "nivel": 5,
                },
                {
                    "sigla": "INF319",
                    "nombre": "Lenguajes Formales",
                    "creditos": 4,
                    "nivel": 5,
                },
            ]

            materias_dict = {}
            for mat_data in materias_data:
                nivel_idx = mat_data["nivel"] - 1
                materia = Materia(
                    sigla=mat_data["sigla"],
                    nombre=mat_data["nombre"],
                    creditos=mat_data["creditos"],
                    es_electiva=mat_data.get("electiva", False),
                    nivel_id=niveles[nivel_idx].id,
                    plan_estudio_id=plan_estudio.id,
                )
                db.add(materia)
                materias_dict[mat_data["sigla"]] = materia

            db.commit()

            # Refresh materias
            for materia in materias_dict.values():
                db.refresh(materia)

            # 5. Crear Prerrequisitos
            print("🔗 Creando prerrequisitos...")
            prerrequisitos = [
                ("MAT101", "MAT102"),
                ("MAT102", "MAT207"),
                ("MAT103", "MAT207"),
                ("FIS100", "FIS102"),
                ("LIN100", "LIN101"),
                ("INF120", "INF210"),
                ("INF120", "INF211"),
                ("INF210", "INF220"),
                ("INF210", "INF221"),
                ("MAT207", "INF205"),
                ("MAT207", "MAT202"),
                ("MAT202", "MAT302"),
                ("INF220", "INF310"),
                ("INF220", "INF312"),
                ("INF119", "INF319"),
            ]

            for sigla_pre, sigla_materia in prerrequisitos:
                if sigla_materia in materias_dict:
                    prerrequisito = Prerrequisito(
                        materia_id=materias_dict[sigla_materia].id,
                        sigla_prerrequisito=sigla_pre,
                    )
                    db.add(prerrequisito)

            db.commit()

            # 6. Crear Docentes
            print("👨‍🏫 Creando docentes...")
            docentes_data = [
                ("María", "Gutiérrez"),
                ("Juan", "Ramírez"),
                ("Ana", "Paredes"),
                ("Luis", "Mendoza"),
                ("Carla", "Rojas"),
                ("Diego", "Cabrera"),
            ]

            docentes = []
            for nombre, apellido in docentes_data:
                docente = Docente(nombre=nombre, apellido=apellido)
                db.add(docente)
                docentes.append(docente)

            db.commit()

            # Refresh docentes
            for docente in docentes:
                db.refresh(docente)

            # 7. Crear Estudiantes
            print("👨‍🎓 Creando estudiantes...")
            estudiantes_data = [
                ("Victor", "Salvatierra", "VIC001", "12345671"),
                ("Tatiana", "Cuéllar", "TAT002", "12345672"),
                ("Gabriel", "Fernández", "GAB003", "12345673"),
                ("Lucía", "Soto", "LUC004", "12345674"),
                ("Álvaro", "Pérez", "ALV005", "12345675"),
                ("Sofía", "Ribas", "SOF006", "12345676"),
                ("Daniel", "Flores", "DAN007", "12345677"),
                ("Carolina", "López", "CAR008", "12345678"),
            ]

            estudiantes = []
            for nombre, apellido, registro, ci in estudiantes_data:
                estudiante = Estudiante(
                    nombre=nombre,
                    apellido=apellido,
                    registro=registro,
                    ci=ci,
                    contraseña=get_password_hash("123456"),  # Password por defecto
                    carrera_id=carrera.id,
                )
                db.add(estudiante)
                estudiantes.append(estudiante)

            db.commit()

            # Refresh estudiantes
            for estudiante in estudiantes:
                db.refresh(estudiante)

            # 8. Crear Aulas
            print("🏫 Creando aulas...")
            aulas_data = [
                ("236", "10"),
                ("236", "12"),
                ("236", "13"),
                ("236", "21"),
                ("236", "22"),
                ("236", "31"),
            ]

            aulas = []
            for modulo, aula_num in aulas_data:
                aula = Aula(modulo=modulo, aula=aula_num)
                db.add(aula)
                aulas.append(aula)

            db.commit()

            # Refresh aulas
            for aula in aulas:
                db.refresh(aula)

            # 9. Crear Horarios
            print("⏰ Creando horarios...")
            horarios_data = [
                ("Lunes", dt_time(8, 0), dt_time(10, 0), aulas[0].id),
                ("Martes", dt_time(10, 0), dt_time(12, 0), aulas[1].id),
                ("Miércoles", dt_time(14, 0), dt_time(16, 0), aulas[2].id),
                ("Jueves", dt_time(16, 0), dt_time(18, 0), aulas[3].id),
                ("Viernes", dt_time(8, 0), dt_time(10, 0), aulas[4].id),
            ]

            horarios = []
            for dia, hora_inicio, hora_final, aula_id in horarios_data:
                horario = Horario(
                    dia=dia,
                    hora_inicio=hora_inicio,
                    hora_final=hora_final,
                    aula_id=aula_id,
                )
                db.add(horario)
                horarios.append(horario)

            db.commit()

            # Refresh horarios
            for horario in horarios:
                db.refresh(horario)

            # 10. Crear Gestiones
            print("📅 Creando gestiones...")
            gestiones_data = [(1, 2025), (2, 2025), (3, 2025), (4, 2025)]

            gestiones = []
            for semestre, año in gestiones_data:
                gestion = Gestion(semestre=semestre, año=año)
                db.add(gestion)
                gestiones.append(gestion)

            db.commit()

            # Refresh gestiones
            for gestion in gestiones:
                db.refresh(gestion)

            # 11. Crear Grupos
            print("👥 Creando grupos...")
            grupos_data = [
                (
                    "INF120-01 Programación I - SEM 2/2025",
                    docentes[0].id,
                    gestiones[1].id,
                    "INF120",
                    horarios[0].id,
                ),
                (
                    "MAT101-01 Cálculo I - SEM 1/2025",
                    docentes[1].id,
                    gestiones[0].id,
                    "MAT101",
                    horarios[1].id,
                ),
                (
                    "INF312-01 Base de Datos I - SEM 2/2025",
                    docentes[2].id,
                    gestiones[1].id,
                    "INF312",
                    horarios[2].id,
                ),
            ]

            grupos = []
            for (
                descripcion,
                docente_id,
                gestion_id,
                sigla_materia,
                horario_id,
            ) in grupos_data:
                if sigla_materia in materias_dict:
                    grupo = Grupo(
                        descripcion=descripcion,
                        docente_id=docente_id,
                        gestion_id=gestion_id,
                        materia_id=materias_dict[sigla_materia].id,
                        horario_id=horario_id,
                    )
                    db.add(grupo)
                    grupos.append(grupo)

            db.commit()

            # Refresh grupos
            for grupo in grupos:
                db.refresh(grupo)

            # 12. Crear Inscripciones
            print("📝 Creando inscripciones...")
            inscripciones_data = [
                (1, gestiones[0].id, estudiantes[0].id, grupos[0].id),
                (1, gestiones[0].id, estudiantes[1].id, grupos[0].id),
                (1, gestiones[0].id, estudiantes[2].id, grupos[0].id),
            ]

            for semestre, gestion_id, estudiante_id, grupo_id in inscripciones_data:
                inscripcion = Inscripcion(
                    semestre=semestre,
                    gestion_id=gestion_id,
                    estudiante_id=estudiante_id,
                    grupo_id=grupo_id,
                )
                db.add(inscripcion)

            db.commit()

            # 13. Crear Notas
            print("📊 Creando notas...")
            notas_data = [
                (78.50, estudiantes[0].id),
                (65.00, estudiantes[1].id),
                (91.00, estudiantes[2].id),
                (84.25, estudiantes[0].id),
                (72.00, estudiantes[1].id),
                (88.00, estudiantes[0].id),
                (74.50, estudiantes[4].id),
                (69.00, estudiantes[5].id),
                (81.00, estudiantes[0].id),
                (70.00, estudiantes[6].id),
                (79.00, estudiantes[0].id),
                (86.50, estudiantes[1].id),
                (60.00, estudiantes[7].id),
            ]

            for nota_valor, estudiante_id in notas_data:
                nota = Nota(nota=nota_valor, estudiante_id=estudiante_id)
                db.add(nota)

            db.commit()

            # 14. Crear Detalles
            print("📋 Creando detalles...")
            detalles_data = [
                (date(2025, 3, 10), dt_time(8, 0), grupos[0].id),
                (date(2025, 3, 17), dt_time(8, 0), grupos[0].id),
                (date(2025, 2, 20), dt_time(10, 0), grupos[1].id),
                (date(2025, 5, 5), dt_time(14, 0), grupos[2].id),
            ]

            for fecha, hora, grupo_id in detalles_data:
                detalle = Detalle(fecha=fecha, hora=hora, grupo_id=grupo_id)
                db.add(detalle)

            db.commit()

            print("✅ Seeding completado exitosamente!")
            print(f"🎓 Carrera creada: {carrera.nombre}")
            print(f"📚 Plan de estudios: {plan_estudio.plan}")
            print(f"📖 Materias creadas: {len(materias_data)}")
            print(f"👨‍🏫 Docentes creados: {len(docentes)}")
            print(f"👨‍🎓 Estudiantes creados: {len(estudiantes)}")
            print(f"👥 Grupos creados: {len(grupos)}")
            print("\n🔐 Credenciales de estudiantes:")
            for est in estudiantes:
                print(f"   📋 {est.registro} / 123456 ({est.nombre} {est.apellido})")

        except Exception as e:
            print(f"❌ Error durante seeding: {e}")
            db.rollback()
            raise


def check_if_seeded(db: Session) -> bool:
    """Verificar si la base de datos ya tiene datos"""
    carreras = db.query(Carrera).all()
    return len(carreras) > 0


def run_seeder():
    """Ejecutar seeder solo si no hay datos"""
    with SessionLocal() as db:
        if check_if_seeded(db):
            print("📊 Base de datos ya tiene datos, saltando seeding...")
            return False

    seed_database()
    return True
