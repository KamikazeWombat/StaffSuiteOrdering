from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship


from config import dec_base


class Attendee(dec_base):
    __tablename__ = "attendee"
    badge_num = Column('badge_num', Integer)
    public_id = Column('public_id', String, primary_key=True)
    badge_printed_name = Column('badge_printed_name', String)
    orders = relationship('Order')
