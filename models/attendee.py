
from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Attendee(Base):
    __tablename__ = "attendee"

    public_id = Column('public_id', String, primary_key=True)
    badge_printed_name = Column('badge_printed_name', String)
    orders = relationship('order', back_populates='attendee')



