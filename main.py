import requests
import json

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import config


def api_login(apiauthkey, api_endpoint, first_name, last_name, email, zip_code):
    """
    Performs login request again Uber API and returns result
    """
    #runs API request
    REQUEST_HEADERS = {'X-Auth-Token': apiauthkey}
    # data being sent to API
    request_data = {'method': 'attendee.login',
                    'params': [first_name, last_name, email, zip_code]}
    request = requests.post(url=api_endpoint, json=request_data, headers=REQUEST_HEADERS)
    response = json.loads(request.text)

    error = 'no_error' #todo: process actual error checking

    return error, response

def main():
    Base = declarative_base()
    #engine = create_engine(config['database_location'])
    #Base.metadata.create_all(bind=engine)
    #Session = sessionmaker(bind=engine)


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()