from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from config import dec_base


class Order(dec_base):
    __tablename__ = "order"

    id = Column('id', Integer, primary_key=True)
    attendee_id = Column(String, ForeignKey('attendee.public_id'))
    attendee = relationship('Attendee', back_populates='orders')
    department_id = Column(String, ForeignKey('department.id'))
    department = relationship('Department', back_populates='orders')
    meal_id = Column(Integer, ForeignKey('meal.id'))
    meal = relationship('Meal', back_populates='orders')
    overridden = Column('overridden', Boolean, default=False)
    locked = Column('locked', Boolean, default=False)  # marked locked when order fulfilment begins
    toggle1 = Column('toggle1', String)
    toggle2 = Column('toggle2', String)
    toggle3 = Column('toggle3', String)
    toggle4 = Column('toggle4', String)
    toppings1 = Column('toppings1', String)
    toppings2 = Column('toppings2', String)
    notes = Column('notes', String(120))  # todo: figure out how long the limit should be

    eligible = False
    allergies = ''

    # todo: possibly add info on when order was created, for reporting interest?
