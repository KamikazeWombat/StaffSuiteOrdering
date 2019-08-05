
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from config import cfg, dec_base
from models import meal, attendee, order

engine = create_engine(cfg.database_location)

print(dec_base.metadata)
dec_base.metadata.create_all(bind=engine)
print('just created tables')
Session = sessionmaker(bind=engine)
session = Session(bind=engine)

