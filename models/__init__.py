
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sqlalchemy.exc

from config import cfg, dec_base
from models import meal, attendee, order, ingredient, department, dept_order, checkin


def create_my_db_engine():
    """
    Creates DB engine based on config settings
    """
    engine = None
    if cfg.db_config["db_type"] == "sqlite":
        if "pool_size" in cfg.db_config and "max_overflow" in cfg.db_config:
            engine = create_engine(cfg.database_location, pool_size=cfg.db_config['pool_size'],
                                   max_overflow=cfg.db_config['max_overflow'])
        else:
            engine = create_engine(cfg.db_config['location'])

    if cfg.db_config['db_type'] == "postgresql+psycopg2" or cfg.db_config['db_type'] == "postgresql":
        engine = create_engine(cfg.db_config['db_type'] + "://" +
                               cfg.db_config['user'] + ":" +
                               cfg.db_config['password'] + "@" +
                               cfg.db_config['location'] + "/" +
                               cfg.db_config['db_name'],
                               pool_size=cfg.db_config['pool_size'],
                               max_overflow=cfg.db_config['max_overflow'])

    return engine

engine = create_my_db_engine()

new_sesh = sessionmaker(bind=engine)

try:
    dec_base.metadata.create_all(bind=engine)

except sqlalchemy.exc.OperationalError as e:
    print('------------------Operational error here means either no database exists or bad user/pass----------------')
    print("Attempting to create blank database")

    if cfg.db_config['db_type'] == "postgresql+psycopg2" or cfg.db_config['db_type'] == "postgresql":
        con = psycopg2.connect(dbname=cfg.db_config['db_name'],
                               user=cfg.db_config['user'], host='',
                               password=cfg.db_config['password'])
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()
        cur.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(cfg.db_config['db_name']))
        )
        # retry table creation after DB creation attempt
        dec_base.metadata.create_all(bind=engine)
