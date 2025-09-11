from sqlalchemy import Column, String, Integer, DateTime, Text, Float, Boolean
from datetime import datetime
from .base import BaseModel
import json


class Task(BaseModel):
    __tablename__ = "tasks"

    # Identificación
    task_id = Column(String(100), unique=True, nullable=False, index=True)
    task_type = Column(String(100), nullable=False)

    # Estado
    status = Column(String(50), nullable=False, default="pending")
    priority = Column(Integer, default=5)

    # Datos
    data = Column(Text, nullable=False)
    result = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    scheduled_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Retry logic
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Progress tracking
    progress = Column(Float, default=0.0)

    # Lock mechanism
    locked_by = Column(String(100), nullable=True)
    locked_at = Column(DateTime, nullable=True)

    # Rollback info
    rollback_data = Column(Text, nullable=True)
    needs_rollback = Column(Boolean, default=False)

    def set_data(self, data_dict):
        self.data = json.dumps(data_dict)

    def get_data(self):
        return json.loads(self.data) if self.data else {}

    def set_result(self, result_dict):
        self.result = json.dumps(result_dict)

    def get_result(self):
        return json.loads(self.result) if self.result else {}

    def set_rollback_data(self, rollback_dict):
        self.rollback_data = json.dumps(rollback_dict)

    def get_rollback_data(self):
        return json.loads(self.rollback_data) if self.rollback_data else {}

    def can_retry(self):
        return self.retry_count < self.max_retries

    def is_locked(self):
        if not self.locked_by or not self.locked_at:
            return False
        lock_timeout = datetime.utcnow() - self.locked_at
        return lock_timeout.total_seconds() < 300

    def lock(self, worker_id: str):
        self.locked_by = worker_id
        self.locked_at = datetime.utcnow()

    def unlock(self):
        self.locked_by = None
        self.locked_at = None
