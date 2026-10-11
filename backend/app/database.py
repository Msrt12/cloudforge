import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def read_secret(name):
    secret_path = Path(f"/var/secrets/{name}")

    if secret_path.exists():
        return secret_path.read_text().strip()

    return None


db_name = read_secret("db-name")
db_user = read_secret("db-user")
db_password = read_secret("db-password")


if db_name and db_user and db_password:
    # GKE + Cloud SQL Auth Proxy
    DATABASE_URL = (
        f"postgresql://{db_user}:{db_password}"
        f"@127.0.0.1:5432/{db_name}"
    )
else:
    # Local development / Docker Compose
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/cloudforge",
    )


engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()