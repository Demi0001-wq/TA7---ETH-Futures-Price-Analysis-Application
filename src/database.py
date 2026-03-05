from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .config import settings
from .models import Base

# setting up the sqlite engine - check_same_thread=False is needed for sqlite + fastapi
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
# this sessionmaker is what we use to talk to the db
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    # helper to create all tables if they don't exist yet
    Base.metadata.create_all(bind=engine)

def get_db():
    # this is a dependency for fastapi routes to get a database session
    db = SessionLocal()
    try:
        yield db
    finally:
        # always close the connection when the request is done
        db.close()
