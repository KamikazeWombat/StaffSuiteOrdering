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
    contact_info = Column('contact_info', String)  # requested contact info for this department for this meal completion
