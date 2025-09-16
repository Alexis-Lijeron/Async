import threading
import queue
import uuid
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from contextlib import contextmanager
from app.core.redis_queue_monitor import redis_monitor
from app.config.database import SessionLocal
from app.models.task import Task


class SyncThreadQueueManager:
    """
    Sistema de colas síncrono usando threading y queue
    """

    def __init__(self):
        self._running = False
        self._workers = []
        self._max_workers = 4
        self._check_interval = 5.0
        self._lock_timeout = timedelta(minutes=5)
        self._task_queue = queue.Queue()
        self._task_notification = threading.Event()

        self._stats = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "tasks_completed": 0,
            "workers_active": 0,
            "uptime_start": None,
            "last_db_check": None,
        }

    def start(self, max_workers: int = 4):
        """Iniciar el sistema de colas con workers síncronos"""
        if self._running:
            print("⚠️ Sistema de colas ya está en ejecución")
            return
        # Inicializar Redis monitor
        try:
            redis_monitor.start()
        except Exception as e:
            print(f"⚠️ Warning: Redis no disponible: {e}")

        self._running = True
        self._max_workers = max_workers
        self._stats["uptime_start"] = datetime.utcnow()
        self._task_notification.clear()

        print(f"🚀 SyncThreadQueueManager iniciando con {max_workers} workers...")

        # Recuperar tareas huérfanas
        self._recover_orphaned_tasks()

        # Iniciar workers como threads
        for i in range(max_workers):
            worker_id = f"worker_{i+1}"
            worker_thread = threading.Thread(
                target=self._run_sync_worker,
                args=(worker_id,),
                daemon=True,
                name=f"QueueWorker-{worker_id}",
            )
            worker_thread.start()
            self._workers.append(worker_thread)
            print(f"🔨 Worker {worker_id} iniciado")

        # Iniciar monitor de tareas
        monitor_thread = threading.Thread(
            target=self._task_monitor, daemon=True, name="TaskMonitor"
        )
        monitor_thread.start()

        print(f"✅ {len(self._workers)} workers iniciados con monitoreo síncrono")
        self._stats["workers_active"] = len(self._workers)

    def stop(self):
        """Detener el sistema de colas"""
        if not self._running:
            return

        print("🛑 Deteniendo SyncThreadQueueManager...")
        self._running = False

        # Despertar workers para que puedan terminar
        self._task_notification.set()

        # Esperar a que terminen los workers
        for worker in self._workers:
            worker.join(timeout=5)

        # Limpiar listas
        self._workers.clear()
        self._stats["workers_active"] = 0

        print("✅ SyncThreadQueueManager detenido")

    def _task_monitor(self):
        """Monitor que revisa periódicamente por nuevas tareas"""
        print("📊 Monitor de tareas iniciado")

        while self._running:
            try:
                # Revisar si hay tareas pendientes cada 10 segundos
                with SessionLocal() as db:
                    pending_count = (
                        db.query(Task).filter(Task.status == "pending").count()
                    )

                    if pending_count > 0:
                        print(f"📋 Monitor detectó {pending_count} tareas pendientes")
                        # Despertar workers si hay tareas
                        self._task_notification.set()

                    self._stats["last_db_check"] = datetime.utcnow()

                # Esperar antes del próximo check
                time.sleep(10.0)  # Check cada 10 segundos

            except Exception as e:
                print(f"❌ Error en monitor: {e}")
                time.sleep(5.0)

        print("🛑 Monitor de tareas detenido")

    def _run_sync_worker(self, worker_id: str):
        """Worker síncrono que espera notificaciones"""
        print(f"🔧 Worker síncrono {worker_id} iniciado")

        while self._running:
            try:
                # Esperar notificación de nuevas tareas
                self._task_notification.wait(timeout=self._check_interval)

                if not self._running:
                    break

                # Procesar tareas disponibles
                tasks_processed = 0
                while self._running:
                    task_processed = self._process_next_task(worker_id)

                    if not task_processed:
                        break  # No hay más tareas

                    tasks_processed += 1

                    # Evitar monopolizar el worker
                    if tasks_processed >= 10:
                        break

                if tasks_processed > 0:
                    print(f"🔄 Worker {worker_id} procesó {tasks_processed} tareas")

                # Reset del evento después de procesar
                if tasks_processed > 0:
                    # Despertar otros workers si procesamos tareas
                    time.sleep(0.1)  # Pequeña pausa
                    self._task_notification.set()
                else:
                    # No hay tareas, limpiar evento
                    self._task_notification.clear()

            except Exception as e:
                print(f"❌ Error en worker {worker_id}: {e}")
                time.sleep(1.0)

        print(f"🛑 Worker síncrono {worker_id} detenido")

    def add_task(
        self,
        task_type: str,
        data: Dict[str, Any],
        priority: int = 5,
        max_retries: int = 3,
        rollback_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Agregar una tarea a la cola y notificar workers"""
        task_id = str(uuid.uuid4())

        with SessionLocal() as db:
            task = Task(
                task_id=task_id,
                task_type=task_type,
                status="pending",
                priority=priority,
                max_retries=max_retries,
                scheduled_at=datetime.utcnow(),
            )

            task.set_data(data)
            if rollback_data:
                task.set_rollback_data(rollback_data)

            db.add(task)
            db.commit()

            print(f"📝 Tarea agregada: {task_id} ({task_type}) [Prioridad: {priority}]")

            # Despertar workers para procesar nueva tarea
            self._task_notification.set()

            return task_id

    def _process_next_task(self, worker_id: str) -> bool:
        """Obtener y procesar la siguiente tarea disponible"""
        try:
            with SessionLocal() as db:
                # Obtener siguiente tarea con bloqueo atómico
                task = self._get_and_lock_task(db, worker_id)

                if not task:
                    return False

                print(f"📋 Worker {worker_id} procesando: {task.task_id}")

                try:
                    # Procesar la tarea
                    self._execute_task(task, worker_id, db)
                    self._stats["tasks_processed"] += 1
                    return True

                except Exception as e:
                    print(f"❌ Error procesando tarea {task.task_id}: {e}")
                    self._handle_task_failure(task, str(e), db)
                    self._stats["tasks_failed"] += 1
                    return True
                finally:
                    db.commit()
        except Exception as e:
            print(f"❌ Error crítico en _process_next_task: {e}")
            return False

    def _get_and_lock_task(self, db: Session, worker_id: str) -> Optional[Task]:
        """Obtener y bloquear atómicamente la siguiente tarea disponible"""
        try:
            # Buscar tareas pendientes o con lock expirado
            lock_expiry = datetime.utcnow() - self._lock_timeout

            task = (
                db.query(Task)
                .filter(
                    and_(
                        Task.status == "pending",
                        or_(Task.locked_by.is_(None), Task.locked_at < lock_expiry),
                    )
                )
                .order_by(Task.priority.asc(), Task.scheduled_at.asc())
                .with_for_update(skip_locked=True)
                .first()
            )

            if task:
                # Bloquear la tarea
                task.status = "processing"
                task.locked_by = worker_id
                task.locked_at = datetime.utcnow()
                task.started_at = datetime.utcnow()
                db.flush()

            return task

        except Exception as e:
            print(f"Error obteniendo tarea: {e}")
            db.rollback()
            return None

    def _execute_task(self, task: Task, worker_id: str, db: Session):
        """Ejecutar una tarea específica"""
        try:
            # Publicar evento de tarea iniciada
            redis_monitor.publish_task_event(
                "task_started",
                task.task_id,
                task.task_type,
                worker_id,
                {"priority": task.priority, "retry_count": task.retry_count},
            )

            # Registrar heartbeat
            redis_monitor.register_worker_heartbeat(worker_id, task.task_id)

            from app.core.task_processors_sync import get_task_processor

            processor = get_task_processor(task.task_type)
            if not processor:
                raise ValueError(f"No hay procesador para el tipo: {task.task_type}")

            # Actualizar progreso
            task.progress = 10.0
            db.flush()

            # Ejecutar procesador
            result = processor(task.get_data(), task)

            # Actualizar progreso
            task.progress = 90.0
            db.flush()

            if result.get("success", False):
                # Tarea completada exitosamente
                task.status = "completed"
                task.set_result(result)
                task.progress = 100.0
                task.completed_at = datetime.utcnow()
                task.unlock()

                self._stats["tasks_completed"] += 1

                # Publicar evento de tarea completada
                redis_monitor.publish_task_event(
                    "task_completed",
                    task.task_id,
                    task.task_type,
                    worker_id,
                    {
                        "result": result,
                        "duration": (
                            datetime.utcnow() - task.started_at
                        ).total_seconds(),
                    },
                )

                print(f"✅ Tarea completada: {task.task_id}")

            else:
                raise Exception(result.get("error", "Error desconocido"))

        except Exception as e:
            # Publicar evento de tarea fallida
            redis_monitor.publish_task_event(
                "task_failed",
                task.task_id,
                task.task_type,
                worker_id,
                {"error": str(e), "retry_count": task.retry_count},
            )
            raise
        finally:
            # Heartbeat sin tarea actual
            redis_monitor.register_worker_heartbeat(worker_id)

    def _handle_task_failure(self, task: Task, error_message: str, db: Session):
        """Manejar fallo de tarea con reintentos"""
        print(f"❌ Tarea falló: {task.task_id} - {error_message}")

        task.error_message = error_message
        task.unlock()

        if task.can_retry():
            # Programar reintento
            task.status = "pending"
            task.retry_count += 1
            task.started_at = None
            # Retraso exponencial para reintentos
            delay = min(30 * (2**task.retry_count), 300)
            task.scheduled_at = datetime.utcnow() + timedelta(seconds=delay)
            print(
                f"🔄 Programando reintento {task.retry_count} para: {task.task_id} (en {delay}s)"
            )
        else:
            # Fallo definitivo
            task.status = "failed"
            task.completed_at = datetime.utcnow()
            task.needs_rollback = True
            print(f"💀 Tarea falló definitivamente: {task.task_id}")

            # Programar rollback si hay datos
            if task.rollback_data:
                self._schedule_rollback(task)

    def _schedule_rollback(self, failed_task: Task):
        """Programar operación de rollback"""
        rollback_data = failed_task.get_rollback_data()
        rollback_data["original_task_id"] = failed_task.task_id

        self.add_task(
            task_type="rollback_operation",
            data=rollback_data,
            priority=1,  # Alta prioridad para rollbacks
        )

        print(f"⪪ Rollback programado para: {failed_task.task_id}")

    def _recover_orphaned_tasks(self):
        """Recuperar tareas huérfanas después de un reinicio"""
        with SessionLocal() as db:
            lock_expiry = datetime.utcnow() - self._lock_timeout

            # Buscar tareas en processing con lock expirado
            orphaned_tasks = (
                db.query(Task)
                .filter(and_(Task.status == "processing", Task.locked_at < lock_expiry))
                .all()
            )

            for task in orphaned_tasks:
                print(f"🔧 Recuperando tarea huérfana: {task.task_id}")
                task.status = "pending"
                task.unlock()
                task.started_at = None

            if orphaned_tasks:
                db.commit()
                print(f"✅ {len(orphaned_tasks)} tareas huérfanas recuperadas")

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Obtener estado de una tarea"""
        with SessionLocal() as db:
            task = db.query(Task).filter(Task.task_id == task_id).first()

            if not task:
                return None

            return {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "status": task.status,
                "priority": task.priority,
                "progress": task.progress,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                "scheduled_at": (
                    task.scheduled_at.isoformat() if task.scheduled_at else None
                ),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": (
                    task.completed_at.isoformat() if task.completed_at else None
                ),
                "error_message": task.error_message,
                "data": task.get_data(),
                "result": task.get_result() if task.result else None,
                "locked_by": task.locked_by,
                "needs_rollback": task.needs_rollback,
            }

    def get_queue_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de la cola"""
        with SessionLocal() as db:
            status_counts = {}
            statuses = ["pending", "processing", "completed", "failed", "cancelled"]

            for status in statuses:
                count = db.query(Task).filter(Task.status == status).count()
                status_counts[status] = count

            uptime = None
            if self._stats["uptime_start"]:
                uptime = datetime.utcnow() - self._stats["uptime_start"]

            return {
                "queue_status": "running" if self._running else "stopped",
                "total_workers": self._max_workers,
                "active_workers": self._stats["workers_active"],
                "task_counts": status_counts,
                "total_tasks": sum(status_counts.values()),
                "uptime_seconds": uptime.total_seconds() if uptime else 0,
                "last_db_check": (
                    self._stats["last_db_check"].isoformat()
                    if self._stats["last_db_check"]
                    else None
                ),
                "stats": self._stats,
            }

    def delete_task(self, task_id: str) -> bool:
        """Eliminar una tarea específica por su ID"""
        with SessionLocal() as db:
            try:
                task = db.query(Task).filter(Task.task_id == task_id).first()

                if not task:
                    print(f"❌ Tarea no encontrada: {task_id}")
                    return False

                db.delete(task)
                db.commit()

                print(f"✅ Tarea eliminada: {task_id}")
                return True

            except Exception as e:
                print(f"❌ Error eliminando tarea {task_id}: {e}")
                db.rollback()
                return False

    def delete_all_tasks(self) -> int:
        """Eliminar todas las tareas de la base de datos, sin importar su estado"""
        with SessionLocal() as db:
            try:
                count = db.query(Task).count()
                db.query(Task).delete()
                db.commit()
                print(f"🧨 {count} tareas eliminadas (todas)")
                return count
            except Exception as e:
                db.rollback()
                print(f"❌ Error eliminando todas las tareas: {e}")
                raise e

    def cleanup_old_tasks(self, days_old: int = 7) -> int:
        """Limpiar tareas antiguas completadas"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        with SessionLocal() as db:
            try:
                old_tasks = (
                    db.query(Task)
                    .filter(
                        and_(
                            Task.status.in_(["completed", "cancelled"]),
                            Task.completed_at < cutoff_date,
                        )
                    )
                    .all()
                )

                count = len(old_tasks)

                for task in old_tasks:
                    db.delete(task)

                db.commit()
                print(f"🧹 {count} tareas antiguas eliminadas")
                return count

            except Exception as e:
                db.rollback()
                print(f"❌ Error limpiando tareas: {e}")
                raise e

    def get_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Obtener lista de tareas con filtros"""
        with SessionLocal() as db:
            query = db.query(Task)

            if status:
                query = query.filter(Task.status == status)
            if task_type:
                query = query.filter(Task.task_type == task_type)

            query = query.order_by(Task.priority.asc(), Task.scheduled_at.desc())
            tasks = query.offset(skip).limit(limit).all()

            return [
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "status": task.status,
                    "priority": task.priority,
                    "progress": task.progress,
                    "scheduled_at": (
                        task.scheduled_at.isoformat() if task.scheduled_at else None
                    ),
                    "started_at": (
                        task.started_at.isoformat() if task.started_at else None
                    ),
                    "completed_at": (
                        task.completed_at.isoformat() if task.completed_at else None
                    ),
                    "retry_count": task.retry_count,
                    "error_message": task.error_message,
                }
                for task in tasks
            ]

    def is_running(self) -> bool:
        return self._running

    def cancel_task(self, task_id: str) -> bool:
        """Cancelar una tarea"""
        with SessionLocal() as db:
            task = (
                db.query(Task)
                .filter(
                    and_(
                        Task.task_id == task_id,
                        Task.status.in_(["pending", "processing"]),
                    )
                )
                .with_for_update()
                .first()
            )

            if not task:
                return False

            task.status = "cancelled"
            task.completed_at = datetime.utcnow()
            task.unlock()

            db.commit()
            print(f"⌛ Tarea cancelada: {task_id}")
            return True

    def retry_task(self, task_id: str) -> bool:
        """Reintentar una tarea fallida"""
        with SessionLocal() as db:
            task = (
                db.query(Task).filter(Task.task_id == task_id).with_for_update().first()
            )

            if not task or task.status != "failed":
                return False

            task.status = "pending"
            task.error_message = None
            task.started_at = None
            task.completed_at = None
            task.unlock()

            db.commit()

            # Despertar workers para procesar la tarea
            self._task_notification.set()

            print(f"🔄 Tarea reintentada manualmente: {task_id}")
            return True


# Instancia global síncrona
sync_thread_queue_manager = SyncThreadQueueManager()
