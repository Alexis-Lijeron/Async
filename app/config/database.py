from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import time
from .settings import settings

# Configurar el motor de la base de datos
engine = create_engine(
    settings.database_url_sync,  # Nueva URL síncrona
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    connect_args={"options": "-c default_transaction_isolation=read_committed"},
)

# Crear una sesión local
SessionLocal = sessionmaker(
    bind=engine, autocommit=False, autoflush=True, expire_on_commit=False
)

Base = declarative_base()


def get_db() -> Session:
    """Obtener una sesión de base de datos con manejo de errores adecuado"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def test_connection(max_retries: int = 5, delay: float = 2.0) -> bool:
    for attempt in range(max_retries):
        try:
            with SessionLocal() as session:
                result = session.execute(text("SELECT 1"))
                session.commit()
                print(f"Database connection successful on attempt {attempt + 1}")
                return True
        except Exception as e:
            print(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("All database connection attempts failed")
                return False
    return False


def wait_for_db(max_wait: int = 60) -> bool:
    print("Waiting for database to be ready...")
    start_time = time.time()

    while True:
        try:
            if test_connection(max_retries=1):
                return True
        except Exception as e:
            print(f"Database not ready: {e}")

        elapsed = time.time() - start_time
        if elapsed > max_wait:
            print(f"Timeout waiting for database after {max_wait} seconds")
            return False

        time.sleep(2)


def init_db():
    try:
        # First, wait for database to be ready
        if not wait_for_db():
            raise Exception("Database is not ready")

        Base.metadata.create_all(bind=engine)

        print("Database tables initialized successfully")
        return True

    except Exception as e:
        print(f"Failed to initialize database: {e}")
        raise e


def close_db():
    try:
        engine.dispose()
        print("Database connections closed")
    except Exception as e:
        print(f"Error closing database connections: {e}")
