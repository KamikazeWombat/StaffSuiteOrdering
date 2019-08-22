from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from config import dec_base

class Ingredient(dec_base):
    """
    An Ingredient for selecting a meal.  "Lettuce", "General Zho's Chicken", "Meat Pizza"
    """
    __tablename__ = 'ingredient'
    id = Column('id', Integer, primary_key=True)
    #meal_id = Column(Integer, ForeignKey('meal.id'))
    label = Column('label', String)
    description = Column('description', String)
