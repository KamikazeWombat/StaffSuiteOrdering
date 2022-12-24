from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
import datetime

from config import dec_base


class Checkin(dec_base):
    __tablename__ = "checkin"

    id = Column('id', Integer, primary_key=True)
    attendee_id = Column(String, ForeignKey('attendee.public_id'))
    attendee = relationship('Attendee', back_populates='checkins')
    meal_id = Column(Integer, ForeignKey('meal.id'))
    meal = relationship('Meal', back_populates='checkins')
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    duplicate = Column(String, default=False)
