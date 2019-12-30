
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import cfg, dec_base
from models import meal, attendee, order, ingredient, department, dept_order, checkin

engine = create_engine(cfg.database_location)
new_sesh = sessionmaker(bind=engine)


dec_base.metadata.create_all(bind=engine)




