from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship

from config import dec_base


class DeptOrder(dec_base):
    __tablename__ = "dept_order"
    
    id = Column('id', Integer, primary_key=True)
    dept_id = Column(String, ForeignKey('department.id'))
    meal_id = Column(Integer, ForeignKey('meal.id'))
    started = Column('started', Boolean, default=False)
    start_time = Column('start_time', DateTime)
    completed = Column('completed', Boolean, default=False)
    completed_time = Column('completed_time', DateTime)
    slack_channel = Column('slack_channel', String, default='')  # what channel bot should message
    slack_contact = Column('slack_contact', String, default='')  # who to ping
    sms_contact = Column('sms_contact', String, default='')  # who to text
    email_contact = Column('email_contact', String, default='')  # who to email
    other_contact = Column('other_contact', String, default='')  # additional contact info
