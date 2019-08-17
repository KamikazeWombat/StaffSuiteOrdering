from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from config import dec_base


class Order(dec_base):
    __tablename__ = "order"

    id = Column('id', Integer, primary_key=True)
    attendee_id = Column(String, ForeignKey('attendee.public_id'))
    attendee = relationship('Attendee', back_populates='orders')
    department_id = Column(String, ForeignKey('department.id'))
    department = relationship('Department', back_populates='orders')  # todo should be relationship to other table
    meal_id = Column(Integer, ForeignKey('meal.id'))
    meal = relationship('Meal', back_populates='orders')
    overridden = Column('overridden', Boolean, default=False)
    toggle1 = Column('toggle1', String)
    toggle2 = Column('toggle2', String)
    toppings = Column('toppings', String)
    # locked = Column('locked', Boolean) # moved this to Meal instead

    notes = Column('notes', String(100))  # todo: figure out how long the limit should be
