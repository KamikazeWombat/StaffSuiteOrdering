import requests
import json

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

API_ENDPOINT = "https://staging-reggie.magfest.org/jsonrpc/"
# https://staging-reggie.magfest.org/api/reference

#read in authentication toke from file instead of hardcoded.  security yall!
authfile = open('authtoken.cfg', 'r')
REQUEST_HEADERS = {'X-Auth-Token':authfile.read()}
#data being sent to API
request_data = {'method':'attendee.search',
               'params':['Test Developer']}
request = requests.post(url = API_ENDPOINT, json = request_data, headers = REQUEST_HEADERS)
response = json.loads(request.text)

Base = declarative_base()
class Attendee(Base):
    __tablename__ = "attendee"

    public_id = Column('public_id', String, primary_key=True)
    badge_printed_name = Column('badge_printed_name', String)

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)

for entry in response['result']:
    session = Session()
    attendee = Attendee()
    attendee.public_id = entry['public_id']
    attendee.badge_printed_name = entry['badge_printed_name']
    print('public_id: %s   name: %s', attendee.public_id, attendee.badge_printed_name)
    session.add(attendee)
    session.commit()

    session.close()

