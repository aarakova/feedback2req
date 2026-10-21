from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def make_database(url: str):
    engine = create_engine(url, pool_pre_ping=True, echo=False, hide_parameters=True)
    return engine, sessionmaker(engine, expire_on_commit=False)
