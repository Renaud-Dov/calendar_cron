import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base



DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_DATABASE = os.getenv("DB_DATABASE", "calendar")
engine = create_engine("postgresql://%s:%s@%s:%s/%s" % (DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_DATABASE),
                       pool_size=20, max_overflow=20)


Base = declarative_base()
session = Session(engine)

# Add models to database
from models import Event
Base.metadata.create_all(engine)


