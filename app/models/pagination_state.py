from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean
from datetime import datetime
from .base import BaseModel
import json


class PaginationState(BaseModel):
    __tablename__ = "pagination_states"

    session_id = Column(String(100), nullable=False, index=True)
    endpoint = Column(String(200), nullable=False)
    query_hash = Column(String(64), nullable=False)

    # Estado actual
    current_page = Column(Integer, default=0)
    items_per_page = Column(Integer, default=20)
    total_items = Column(Integer, default=0)
    last_accessed = Column(DateTime, default=datetime.utcnow)

    # Parámetros de consulta
    query_params = Column(Text)

    # Tracking de elementos devueltos
    returned_items = Column(Text)

    # Control de expiración
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

    def set_query_params(self, params_dict):
        self.query_params = json.dumps(params_dict, default=str)

    def get_query_params(self):
        return json.loads(self.query_params) if self.query_params else {}

    def set_returned_items(self, item_ids):
        self.returned_items = json.dumps(item_ids, default=str)

    def get_returned_items(self):
        return json.loads(self.returned_items) if self.returned_items else []

    def add_returned_items(self, new_item_ids):
        current_items = self.get_returned_items()
        current_items.extend(new_item_ids)
        self.set_returned_items(current_items)

    def is_expired(self):
        return self.expires_at and datetime.utcnow() > self.expires_at
