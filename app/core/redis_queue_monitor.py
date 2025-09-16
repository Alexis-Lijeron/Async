import redis
import json
import threading
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import uuid

from app.config.settings import settings


@dataclass
class QueueEvent:
    event_id: str
    event_type: (
        str  # task_created, task_started, task_completed, task_failed, queue_stats
    )
    timestamp: datetime
    task_id: Optional[str] = None
    task_type: Optional[str] = None
    worker_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    def to_dict(self):
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


class RedisQueueMonitor:
    """
    Sistema de monitoreo en tiempo real de la cola usando Redis
    """

    def __init__(self, redis_url: str = None):
        import os

        if redis_url is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()
        self.running = False
        self.publisher_thread = None

        # Claves Redis
        self.QUEUE_STATS_KEY = "queue:stats"
        self.TASK_EVENTS_KEY = "queue:task_events"
        self.ACTIVE_WORKERS_KEY = "queue:active_workers"
        self.QUEUE_EVENTS_CHANNEL = "queue:events"

        # Configuración
        self.stats_update_interval = 2  # segundos
        self.max_events_history = 1000

    def start(self):
        """Iniciar el monitor Redis"""
        if self.running:
            return

        try:
            # Probar conexión
            self.redis_client.ping()
            print("✅ Conexión Redis establecida")

            self.running = True

            # Inicializar datos
            self._initialize_redis_data()

            # Iniciar thread de publicación de estadísticas
            self.publisher_thread = threading.Thread(
                target=self._stats_publisher, daemon=True, name="RedisStatsPublisher"
            )
            self.publisher_thread.start()

            print("🚀 Redis Queue Monitor iniciado")

        except redis.ConnectionError as e:
            print(f"❌ Error conectando a Redis: {e}")
            raise

    def stop(self):
        """Detener el monitor"""
        self.running = False
        if self.publisher_thread and self.publisher_thread.is_alive():
            self.publisher_thread.join(timeout=5)
        print("🛑 Redis Queue Monitor detenido")

    def _initialize_redis_data(self):
        """Inicializar estructuras de datos en Redis"""
        # Limpiar datos anteriores
        self.redis_client.delete(
            self.QUEUE_STATS_KEY, self.TASK_EVENTS_KEY, self.ACTIVE_WORKERS_KEY
        )

        # Configurar expiración para eventos
        self.redis_client.expire(self.TASK_EVENTS_KEY, 3600)  # 1 hora

    def _stats_publisher(self):
        """Thread que publica estadísticas periódicamente"""
        while self.running:
            try:
                # Obtener estadísticas del queue manager
                from app.core.thread_queue_sync import sync_thread_queue_manager

                if sync_thread_queue_manager.is_running():
                    stats = sync_thread_queue_manager.get_queue_stats()

                    # Actualizar Redis con estadísticas actuales
                    redis_stats = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "queue_status": stats.get("queue_status", "stopped"),
                        "total_workers": stats.get("total_workers", 0),
                        "active_workers": stats.get("active_workers", 0),
                        "task_counts": stats.get("task_counts", {}),
                        "uptime_seconds": stats.get("uptime_seconds", 0),
                        "tasks_processed": stats.get("tasks_processed", 0),
                        "tasks_failed": stats.get("tasks_failed", 0),
                        "memory_usage": self._get_memory_usage(),
                        "cpu_usage": self._get_cpu_usage(),
                    }

                    # Guardar en Redis
                    self.redis_client.setex(
                        self.QUEUE_STATS_KEY,
                        30,  # TTL de 30 segundos
                        json.dumps(redis_stats),
                    )

                    # Publicar evento de estadísticas
                    event = QueueEvent(
                        event_id=str(uuid.uuid4())[:8],
                        event_type="queue_stats",
                        timestamp=datetime.utcnow(),
                        data=redis_stats,
                    )

                    self._publish_event(event)

                time.sleep(self.stats_update_interval)

            except Exception as e:
                print(f"Error en stats_publisher: {e}")
                time.sleep(self.stats_update_interval)

    def publish_task_event(
        self,
        event_type: str,
        task_id: str,
        task_type: str = None,
        worker_id: str = None,
        data: Dict[str, Any] = None,
    ):
        """Publicar evento de tarea"""
        if not self.running:
            return

        event = QueueEvent(
            event_id=str(uuid.uuid4())[:8],
            event_type=event_type,
            timestamp=datetime.utcnow(),
            task_id=task_id,
            task_type=task_type,
            worker_id=worker_id,
            data=data or {},
        )

        self._publish_event(event)
        self._store_event(event)

    def _publish_event(self, event: QueueEvent):
        """Publicar evento al canal Redis"""
        try:
            self.redis_client.publish(
                self.QUEUE_EVENTS_CHANNEL, json.dumps(event.to_dict())
            )
        except Exception as e:
            print(f"Error publicando evento: {e}")

    def _store_event(self, event: QueueEvent):
        """Almacenar evento en Redis para historial"""
        try:
            # Agregar al historial de eventos
            self.redis_client.lpush(self.TASK_EVENTS_KEY, json.dumps(event.to_dict()))

            # Mantener solo los últimos N eventos
            self.redis_client.ltrim(
                self.TASK_EVENTS_KEY, 0, self.max_events_history - 1
            )

        except Exception as e:
            print(f"Error almacenando evento: {e}")

    def get_current_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas actuales desde Redis"""
        try:
            stats_json = self.redis_client.get(self.QUEUE_STATS_KEY)
            if stats_json:
                return json.loads(stats_json)
            return {}
        except Exception as e:
            print(f"Error obteniendo estadísticas: {e}")
            return {}

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtener eventos recientes"""
        try:
            events = self.redis_client.lrange(self.TASK_EVENTS_KEY, 0, limit - 1)
            return [json.loads(event) for event in events]
        except Exception as e:
            print(f"Error obteniendo eventos: {e}")
            return []

    def get_active_workers(self) -> List[Dict[str, Any]]:
        """Obtener información de workers activos"""
        try:
            workers_data = self.redis_client.hgetall(self.ACTIVE_WORKERS_KEY)
            workers = []

            for worker_id, data_json in workers_data.items():
                worker_data = json.loads(data_json)
                # Verificar si el worker está activo (heartbeat reciente)
                last_heartbeat = datetime.fromisoformat(
                    worker_data.get("last_heartbeat", "")
                )
                if datetime.utcnow() - last_heartbeat < timedelta(minutes=2):
                    workers.append({"worker_id": worker_id, **worker_data})

            return workers
        except Exception as e:
            print(f"Error obteniendo workers: {e}")
            return []

    def register_worker_heartbeat(self, worker_id: str, current_task: str = None):
        """Registrar heartbeat de worker"""
        if not self.running:
            return

        try:
            worker_data = {
                "last_heartbeat": datetime.utcnow().isoformat(),
                "current_task": current_task,
                "status": "active" if current_task else "idle",
            }

            self.redis_client.hset(
                self.ACTIVE_WORKERS_KEY, worker_id, json.dumps(worker_data)
            )

            # Expirar entrada de worker después de 5 minutos
            self.redis_client.expire(self.ACTIVE_WORKERS_KEY, 300)

        except Exception as e:
            print(f"Error registrando heartbeat: {e}")

    def _get_memory_usage(self) -> float:
        """Obtener uso de memoria del proceso"""
        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            return 0.0
        except Exception:
            return 0.0

    def _get_cpu_usage(self) -> float:
        """Obtener uso de CPU del proceso"""
        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            return process.cpu_percent()
        except ImportError:
            return 0.0
        except Exception:
            return 0.0


# Instancia global
redis_monitor = RedisQueueMonitor()
