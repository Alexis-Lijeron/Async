import asyncio
import uuid
from typing import Dict, Any, Optional
from datetime import datetime


class TaskQueue:
    """Sistema de colas asíncrono simple en memoria"""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.pending_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def connect(self):
        """Conectar (simulado para compatibilidad)"""
        self._running = True
        print("✅ Task queue iniciado (en memoria)")

    async def disconnect(self):
        """Desconectar"""
        self._running = False

    async def add_task(self, task_type: str, data: Dict[str, Any]) -> str:
        """Agregar una tarea a la cola"""
        task_id = str(uuid.uuid4())
        task_data = {
            "id": task_id,
            "type": task_type,
            "status": "pending",
            "data": data,
            "result": None,
            "error": None,
            "created_at": datetime.utcnow(),
        }

        # Guardar en memoria
        self.tasks[task_id] = task_data

        # Agregar a la cola
        await self.pending_queue.put(task_id)

        print(f"📝 Tarea agregada: {task_id} ({task_type})")
        return task_id

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Obtener el estado de una tarea"""
        return self.tasks.get(task_id)

    async def update_task_status(
        self, task_id: str, status: str, result: Any = None, error: str = None
    ):
        """Actualizar el estado de una tarea"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = status
            if result is not None:
                self.tasks[task_id]["result"] = str(result)
            if error is not None:
                self.tasks[task_id]["error"] = error

            print(f"🔄 Tarea {task_id}: {status}")

    async def get_next_task(self) -> Optional[str]:
        """Obtener siguiente tarea de la cola"""
        try:
            # Esperar por una tarea con timeout de 1 segundo
            task_id = await asyncio.wait_for(self.pending_queue.get(), timeout=1.0)
            return task_id
        except asyncio.TimeoutError:
            return None

    def get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Obtener datos de una tarea"""
        return self.tasks.get(task_id)


# Instancia global del queue
task_queue = TaskQueue()
