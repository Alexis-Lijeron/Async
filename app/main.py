import atexit
import threading
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import contextmanager

from app.core.thread_queue_sync import sync_thread_queue_manager
from app.core.pagination_system_sync import sync_smart_paginator
from app.core.seeder_sync import run_seeder
from app.config.database import init_db
# Import routers
from app.api.auth import router as auth_router
from app.api.v1.estudiantes import router as estudiantes_router
from app.api.v1.carreras import router as carreras_router
from app.api.v1.materias import router as materias_router
from app.api.v1.docentes import router as docentes_router
from app.api.v1.grupos import router as grupos_router
from app.api.v1.inscripciones import router as inscripciones_router
from app.api.v1.horarios import router as horarios_router
from app.api.v1.aulas import router as aulas_router
from app.api.v1.gestiones import router as gestiones_router
from app.api.v1.notas import router as notas_router

# Router de cola síncrono
from app.api.v1.queue_management import router as queue_router


def initialize_app():
    """Inicializar la aplicación de forma síncrona"""
    print("🚀 Iniciando Sistema Académico SÍNCRONO v3.0...")

    try:
        # 1. Inicializar base de datos con manejo de errores robusto
        print("📊 Inicializando base de datos...")
        try:
            init_db()
            print("✅ Base de datos inicializada correctamente")
        except Exception as db_error:
            print(f"❌ Error crítico en base de datos: {db_error}")
            raise db_error

        # 2. Ejecutar seeding con manejo de errores mejorado
        print("🌱 Ejecutando seeding...")
        try:
            seeded = run_seeder()
            if seeded:
                print("✅ Datos iniciales creados")
            else:
                print("ℹ️ Base de datos ya contiene datos")
        except Exception as seed_error:
            print(f"⚠️ Error en seeding (continuando): {seed_error}")

        # 3. Iniciar sistema de colas síncrono
        print("🧵 Iniciando sistema de colas síncrono...")
        try:
            sync_thread_queue_manager.start(max_workers=1)
            print("✅ Sistema de colas síncrono iniciado")
        except Exception as queue_error:
            print(f"⚠️ Error iniciando colas síncronas: {queue_error}")

        # 4. Limpiar sesiones expiradas
        try:
            cleaned_sessions = sync_smart_paginator.cleanup_expired_sessions()
            if cleaned_sessions > 0:
                print(f"🧹 {cleaned_sessions} sesiones de paginación limpiadas")
        except Exception as cleanup_error:
            print(f"⚠️ Error en limpieza de sesiones: {cleanup_error}")

        # 5. Mostrar estadísticas de inicio
        try:
            if sync_thread_queue_manager.is_running():
                stats = sync_thread_queue_manager.get_queue_stats()
                print(f"🔧 Workers síncronos activos: {stats['total_workers']}")
                print(f"📋 Tareas en cola: {stats['task_counts'].get('pending', 0)}")
                print(f"📊 Última verificación BD: {stats.get('last_db_check', 'N/A')}")
        except Exception as stats_error:
            print(f"⚠️ Error obteniendo estadísticas: {stats_error}")

        print("🎉 Sistema síncrono listo!")

    except Exception as e:
        print(f"❌ Error crítico durante inicialización: {e}")
        print("❌ Aplicación no puede continuar")
        raise e


# Inicializar la aplicación al importar
initialize_app()

app = FastAPI(
    title="Sistema Académico SÍNCRONO API",
    description="""
    ## Sistema Académico SÍNCRONO v3.0 🎓
    
    ### **Cambios a Versión Síncrona:**
    - 🔄 **Threading Queue** - Sistema de colas con threading
    - 🗄️ **SQLAlchemy Síncrono** - psycopg2 en lugar de asyncpg
    - 📄 **Paginación Síncrona** - Sin async/await
    - 🛡️ **Manejo de errores síncrono** - Sistema resiliente
    - ⚡ **Mejor rendimiento** - Menos overhead de async
    
    ### **Credenciales de Prueba:**
    - VIC001 / 123456 (Victor Salvatierra)
    - TAT002 / 123456 (Tatiana Cuéllar)
    - GAB003 / 123456 (Gabriel Fernández)
    - LUC004 / 123456 (Lucía Soto)
    
    ### **Endpoints Principales:**
    - `/queue/` - Gestión de colas síncronas
    - `/queue/tasks` - Paginación síncrona de tareas
    - `/queue/status` - Estadísticas en tiempo real
    - `/queue/cleanup` - Limpieza funcional
    """,
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir todos los routers con manejo de errores
try:
    app.include_router(auth_router, prefix="/auth", tags=["🔐 Autenticación"])
    app.include_router(
        estudiantes_router, prefix="/api/v1/estudiantes", tags=["👨‍🎓 Estudiantes"]
    )
    app.include_router(carreras_router, prefix="/api/v1/carreras", tags=["🎓 Carreras"])
    app.include_router(materias_router, prefix="/api/v1/materias", tags=["📚 Materias"])
    app.include_router(
        docentes_router, prefix="/api/v1/docentes", tags=["👨‍🏫 Docentes"]
    )
    app.include_router(grupos_router, prefix="/api/v1/grupos", tags=["👥 Grupos"])
    app.include_router(
        inscripciones_router, prefix="/api/v1/inscripciones", tags=["📝 Inscripciones"]
    )
    app.include_router(horarios_router, prefix="/api/v1/horarios", tags=["⏰ Horarios"])
    app.include_router(aulas_router, prefix="/api/v1/aulas", tags=["🏫 Aulas"])
    app.include_router(
        gestiones_router, prefix="/api/v1/gestiones", tags=["📅 Gestiones"]
    )
    app.include_router(notas_router, prefix="/api/v1/notas", tags=["📊 Notas"])
    app.include_router(queue_router, prefix="/queue", tags=["🧵 Sistema de Colas"])

    print("✅ Todos los routers cargados correctamente")

except Exception as router_error:
    print(f"❌ Error cargando routers: {router_error}")
    raise router_error


@app.get("/", tags=["🏠 General"])
def root():
    """Información general del sistema síncrono"""
    try:
        if sync_thread_queue_manager.is_running():
            stats = sync_thread_queue_manager.get_queue_stats()
            queue_info = {
                "queue_status": stats["queue_status"],
                "active_workers": stats["active_workers"],
                "total_tasks": stats["total_tasks"],
                "last_db_check": stats.get("last_db_check"),
                "uptime_seconds": stats.get("uptime_seconds", 0),
            }
        else:
            queue_info = {
                "queue_status": "stopped",
                "active_workers": 0,
                "total_tasks": 0,
                "last_db_check": None,
                "uptime_seconds": 0,
            }
    except Exception as e:
        queue_info = {
            "queue_status": "error",
            "active_workers": 0,
            "total_tasks": 0,
            "error": str(e),
        }

    return {
        "message": "Sistema Académico SÍNCRONO API v3.0",
        "status": "running",
        "docs": "/docs",
        **queue_info,
        "features": [
            "🔄 Threading Queue con workers síncronos",
            "🗄️ SQLAlchemy síncrono con psycopg2",
            "📄 Paginación síncrona optimizada",
            "🛡️ Manejo de errores resiliente",
            "⚡ Mejor rendimiento sin overhead async",
            "🔐 Autenticación JWT completa",
            "📚 25+ materias de Ing. Informática",
            "👥 8 usuarios de prueba",
        ],
        "credenciales_prueba": [
            "VIC001/123456 (Victor)",
            "TAT002/123456 (Tatiana)",
            "GAB003/123456 (Gabriel)",
            "LUC004/123456 (Lucía)",
        ],
        "sync_conversion": [
            "Convertido de asyncpg a psycopg2",
            "Reemplazado async/await con threading",
            "Optimizado para operaciones síncronas",
            "Mejorado rendimiento general",
            "Simplificado manejo de concurrencia",
        ],
    }


@app.get("/health", tags=["🏠 General"])
def health_check():
    """Verificación de salud del sistema síncrono"""
    health_data = {
        "status": "healthy",
        "service": "academic-api-sync",
        "version": "3.0.0",
        "timestamp": "2025-09-11T19:15:27Z",
        "mode": "synchronous",
    }

    try:
        if sync_thread_queue_manager.is_running():
            stats = sync_thread_queue_manager.get_queue_stats()
            health_data.update(
                {
                    "queue_status": stats["queue_status"],
                    "workers_active": stats["active_workers"],
                    "tasks_pending": stats["task_counts"].get("pending", 0),
                    "tasks_completed": stats["task_counts"].get("completed", 0),
                    "tasks_failed": stats["task_counts"].get("failed", 0),
                    "uptime_seconds": stats["uptime_seconds"],
                    "last_db_check": stats.get("last_db_check"),
                }
            )
        else:
            health_data.update(
                {
                    "queue_status": "stopped",
                    "workers_active": 0,
                    "tasks_pending": 0,
                    "note": "Queue system not running",
                }
            )
    except Exception as e:
        health_data.update(
            {
                "status": "degraded",
                "queue_error": str(e),
            }
        )

    return health_data


@app.get("/info", tags=["🏠 General"])
def system_info():
    """Información detallada del sistema síncrono"""
    try:
        queue_info = {"status": "stopped"}
        if sync_thread_queue_manager.is_running():
            queue_stats = sync_thread_queue_manager.get_queue_stats()
            queue_info = {
                "status": queue_stats["queue_status"],
                "total_workers": queue_stats["total_workers"],
                "active_workers": queue_stats["active_workers"],
                "task_counts": queue_stats["task_counts"],
                "uptime_seconds": queue_stats["uptime_seconds"],
                "last_db_check": queue_stats.get("last_db_check"),
                "mode": "synchronous",
                "threading_model": "native_threads",
            }

        return {
            "system": {
                "name": "Sistema Académico SÍNCRONO",
                "version": "3.0.0",
                "database": "PostgreSQL con psycopg2",
                "queue_system": "SyncThreadQueue con threading nativo",
                "pagination": "SyncSmartPaginator",
                "auth": "JWT con FastAPI Security",
                "mode": "synchronous",
            },
            "queue": queue_info,
            "sync_advantages": {
                "simpler_debugging": True,
                "better_cpu_utilization": True,
                "reduced_memory_overhead": True,
                "native_threading": True,
                "easier_deployment": True,
            },
            "capabilities": {
                "sync_operations": True,
                "persistent_queue": sync_thread_queue_manager.is_running(),
                "intelligent_pagination": True,
                "automatic_rollback": sync_thread_queue_manager.is_running(),
                "real_time_monitoring": True,
                "fault_recovery": True,
                "bulk_operations": True,
                "optimized_performance": True,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


# Demo de paginación síncrona
@app.get("/demo/pagination-sync", tags=["🎯 Demo"])
def demo_pagination_sync(session_id: str = "demo-sync"):
    """Demostración del sistema de paginación síncrono"""
    try:
        from app.models.estudiante import Estudiante
        from app.config.database import SessionLocal

        def query_estudiantes_demo(db, offset: int, limit: int, **kwargs):
            estudiantes = db.query(Estudiante).offset(offset).limit(limit).all()
            return [
                {
                    "id": e.id,
                    "registro": e.registro,
                    "nombre": e.nombre,
                    "apellido": e.apellido,
                }
                for e in estudiantes
            ]

        results, metadata = sync_smart_paginator.get_next_page(
            session_id=session_id,
            endpoint="demo_pagination_sync",
            query_function=query_estudiantes_demo,
            query_params={},
            page_size=3,
        )

        return {
            "message": "Demostración de paginación SÍNCRONA",
            "instruction": "Llama este endpoint varias veces con el mismo session_id",
            "sync_benefits": [
                "Más simple de debuggear",
                "Mejor utilización de CPU",
                "Menor overhead de memoria",
                "Threading nativo",
            ],
            "data": results,
            "pagination": metadata,
            "next_call": f"/demo/pagination-sync?session_id={session_id}",
        }
    except Exception as e:
        return {
            "error": f"Error en demo: {str(e)}",
            "message": "Demostración con manejo de errores síncrono",
            "fallback_data": [],
            "pagination": {
                "error": str(e),
                "session_id": session_id,
                "has_more_pages": False,
            },
        }


# Endpoint de prueba para queue síncrono
@app.post("/demo/test-sync-queue", tags=["🎯 Demo"])
def test_sync_queue():
    """Probar el sistema de colas síncrono"""
    try:
        if not sync_thread_queue_manager.is_running():
            return {
                "error": "Sistema de colas no está ejecutándose",
                "suggestion": "Usar POST /queue/start para iniciarlo",
            }

        # Crear una tarea de prueba
        task_id = sync_thread_queue_manager.add_task(
            task_type="test_task",
            data={
                "message": "Prueba del sistema síncrono",
                "timestamp": "2025-09-11",
            },
            priority=3,
        )

        return {
            "message": "Tarea de prueba creada en sistema síncrono",
            "task_id": task_id,
            "sync_benefits": [
                "Workers con threading nativo",
                "Mejor utilización de recursos",
                "Debugging más simple",
                "Menor complejidad de código",
            ],
            "check_status": f"/queue/tasks/{task_id}",
        }

    except Exception as e:
        return {
            "error": f"Error creando tarea de prueba: {str(e)}",
            "system_status": "degraded",
        }


def cleanup_on_exit():
    """Limpiar recursos al cerrar"""
    try:
        if sync_thread_queue_manager.is_running():
            sync_thread_queue_manager.stop()
            print("✅ Limpieza síncrona completada")
    except Exception as e:
        print(f"⚠️ Error en limpieza: {e}")


atexit.register(cleanup_on_exit)
