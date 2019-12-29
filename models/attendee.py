from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship


from config import dec_base


class Attendee(dec_base):
    __tablename__ = "attendee"
    badge_num = Column('badge_num', Integer)
    public_id = Column('public_id', String, primary_key=True)
    full_name = Column('full_name', String)
    webhook_url = Column('webhook_url', String, default='')
    webhook_data = Column('webhook_data', String, default='')
    orders = relationship('Order')
    checkins = relationship('Checkin')