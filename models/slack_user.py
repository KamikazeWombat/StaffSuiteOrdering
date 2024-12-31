from sqlalchemy import Column, String


from config import dec_base


class Slack_User(dec_base):
    __tablename__ = "slack_user"

    id = Column('id', String, primary_key=True)
    name = Column('name', String)
    display_name = Column('display_name', String)
    real_name = Column('real_name', String)
