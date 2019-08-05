from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from config import dec_base


class Meal(dec_base):
    __tablename__ = 'meal'
    print('top of Meal class')
    id = Column('id', Integer, primary_key=True)
    meal_name = Column('meal_name', String)
    start_time = Column('start_time', DateTime)
    end_time = Column('end_time', DateTime)
    cutoff = Column('cutoff', DateTime)
    description = Column('description', String)
    #detail_link = Column('detail_link', String)
    #options = list of option objects? #todo:setup options/toppings using multichoice objects
    #uber/configspec.ini [enums] section contains sample item definitions.
    #read the dang title section!!

    #toppings_title = Column('toppings_title', String)
    #toppings_id = Column('toppings_id', )
    #toppings = relationship('Topping')
    orders = relationship('Order')