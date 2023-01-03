
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sqlalchemy.exc

from config import cfg, dec_base
from models import meal, attendee, order, ingredient, department, dept_order, checkin

# todo: hardcoded for now, needs to be added to config
engine = create_engine(cfg.database_location, pool_size=25, max_overflow=50)

new_sesh = sessionmaker(bind=engine)

try:
    dec_base.metadata.create_all(bind=engine)

except sqlalchemy.exc.OperationalError as e:
    print('------------------Operational error here means either no database exists or bad user/pass----------------')
    print("Attempting to create blank database")
    con = psycopg2.connect(dbname='postgres',
                           user='postgres', host='',
                           password='password')
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = con.cursor()
    cur.execute(sql.SQL("CREATE DATABASE {}").format(
        sql.Identifier('testdb2023'))
    )
    # retry table creation after DB creation attempt
    dec_base.metadata.create_all(bind=engine)




