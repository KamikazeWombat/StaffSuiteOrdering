from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from config import dec_base


class Department(dec_base):
    __tablename__ = "department"
    
    id = Column('id', String, primary_key=True)
    name = Column('name', String)
    orders = relationship('Order')
    # todo: contact info here?  or separately for each department order?
