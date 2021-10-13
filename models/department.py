from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from config import dec_base


class Department(dec_base):
    __tablename__ = "department"
    
    id = Column('id', String, primary_key=True)
    name = Column('name', String)
    orders = relationship('Order')
    """below is the default contact info for this department.
    The system will bother DHs when they look at a department page reminding them to configure this
    When the department order for a meal is created it will use these fields to populate the contact info"""
    slack_channel = Column('slack_channel', String, default='')  # what channel bot should message
    slack_contact = Column('slack_contact', String, default='')  # who to ping
    sms_contact = Column('sms_contact', String, default='')  # who to text
    email_contact = Column('email_contact', String, default='')  # who to email
    other_contact = Column('other_contact', String, default='')  # additional contact info
