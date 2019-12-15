from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from config import dec_base


class Department(dec_base):
    __tablename__ = "department"
    
    id = Column('id', String, primary_key=True)
    name = Column('name', String)
    orders = relationship('Order')
    slack_channel = Column('slack_channel', String, default='')  # what channel bot should message
    slack_contact = Column('slack_contact', String, default='')  # who to ping
    text_contact = Column('text_contact', String, default='')  # who to text
    email_contact = Column('email_contact', String, default='')  # who to email
    other_contact = Column('other_contact', String, default='')  # requested contact info for this department for this meal bundle
    """below is the default contact info for this department.
    The system will bother any DH for this department"""
    slack_channel = Column('slack_channel', String, default='')  # what channel bot should message
    slack_contact = Column('slack_contact', String, default='')  # who to ping
    text_contact = Column('text_contact', String, default='')  # who to text
    email_contact = Column('email_contact', String, default='')  # who to email
    other_contact = Column('other_contact', String,
                           default='')  # requested contact info for this department for this meal bundle
