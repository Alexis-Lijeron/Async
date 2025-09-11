from typing import Optional, Dict, Any
from datetime import datetime


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Formatear datetime para respuestas JSON"""
    if dt:
        return dt.isoformat()
    return None


def validate_registro_format(registro: str) -> bool:
    """Validar formato de registro de estudiante"""
    return len(registro) >= 6 and registro.isalnum()


def validate_ci_format(ci: str) -> bool:
    """Validar formato de CI"""
    return len(ci) >= 7 and ci.isdigit()


class ResponseFormatter:
    """Formateador de respuestas estándar"""

    @staticmethod
    def success(data: Any, message: str = "Operación exitosa") -> Dict[str, Any]:
        return {"success": True, "message": message, "data": data}

    @staticmethod
    def error(message: str, error_code: str = None) -> Dict[str, Any]:
        response = {"success": False, "message": message}
        if error_code:
            response["error_code"] = error_code
        return response
