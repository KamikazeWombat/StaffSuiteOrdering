from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from config import dec_base


class Department(dec_base):
    __tablename__ = "department"
    
    id = Column('id', String, primary_key=True)
    name = Column('name', String)
    orders = relationship('Order')
    contact_info = Column('contact_info', String)  # requested contact info for this department for all meals completion
    # todo: contact info here?  or separately for each department order?  both?!
