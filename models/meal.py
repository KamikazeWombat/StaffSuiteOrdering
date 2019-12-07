from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship

from config import dec_base


class Meal(dec_base):
    """
    Meal object, like 'this is what we are serving for the lunch meal on this date'
    """
    __tablename__ = 'meal'
    id = Column('id', Integer, primary_key=True)
    meal_name = Column('meal_name', String)
    start_time = Column('start_time', DateTime)
    end_time = Column('end_time', DateTime)
    cutoff = Column('cutoff', DateTime)
    locked = Column('locked', Boolean, default=False)  # marked locked when order fulfilment starts todo: probably remove
    description = Column('description', String)
    detail_link = Column('detail_link', String)

    toggle1 = Column('toggle1', String)
    toggle1_title = Column('toggle1_name', String)
    toggle2 = Column('toggle2', String)
    toggle2_title = Column('toggle2_name', String)
    toggle3 = Column('toggle3', String)
    toggle3_title = Column('toggle3_name', String)

    toppings = Column('toppings', String)
    toppings_title = Column('toppings_title', String)
    orders = relationship('Order')
    # below used for page display purposes
    eligible = False
    order_exists = False
    overridden = False
