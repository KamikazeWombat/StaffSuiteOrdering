
from sqlalchemy import create_engine

from config import cfg, dec_base
from models import meal, attendee, order

engine = create_engine(cfg.database_location)


dec_base.metadata.create_all(bind=engine)




