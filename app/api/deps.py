from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.core.security import verify_token

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Obtener usuario actual desde el token JWT 
    """
    from app.models.estudiante import Estudiante  # Importar aquí para evitar ciclos

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Verificar token
    registro = verify_token(credentials.credentials)
    if registro is None:
        raise credentials_exception

    # Buscar usuario en la base de datos
    user = db.query(Estudiante).filter(Estudiante.registro == registro).first()

    if user is None:
        raise credentials_exception

    return user


def get_current_active_user(current_user=Depends(get_current_user)):
    """
    Obtener usuario activo (se puede extender para verificar si está activo)
    """
    return current_user
