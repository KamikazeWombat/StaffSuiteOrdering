from sqlalchemy import Column, Integer, String, DateTime
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
    description = Column('description', String)
    #detail_link = Column('detail_link', String)
    #toggles are string fields with a comma separated list of topping names, like "Chicken,Tofu"
    toggle1 = Column('toggle1', String)
    toggle1_title = Column('toggle1_name', String)
    #toggle2 = Column('toggle1', String)
    #toggle2_title = Column('toggle1_name', String)



    #this is a string field with a comma separated list of topping names, like "ketchup,mustard,balogna"
    toppings = Column('toppings', String)
    toppings_title = Column('toppings_title', String)
    #toppings_id = Column('toppings_id', )
    #toppings = relationship('Topping')
    orders = relationship('Order')