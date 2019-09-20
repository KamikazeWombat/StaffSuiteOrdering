import json
import os
import requests

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.declarative import declarative_base


# todo: add configs for settings related to min time for eligibility
class Config:
    """
    Class to make config data easily accessible
    """
    """apiauthkey = ''  # api key for Uber
    api_endpoint = ''  # location for Uber APi
    database_location = ''
    order_message = ''
    orders_open = ''  # todo: probably needs to be function rather than simple attribute
    sticker_count = ''  # how many stickers will print from each time pressing 'print' button
    multi_select_count = ''  # how many lines to do in the multi select section when editing a Meal
    radio_select_count = ''  # how many options in single option selects when editing
    schedule_tolerance = ''  # Tolerance in minutes for shift calculations for start/end of things not lining up exactly
    # todo: system may need separate tolerance for connecting shifts together?
    cherrypy = ''  # cherrypy config dict
    """

    def __init__(self):
        # read in config from files.  todo: option to load other config files than default
        authfile = open('authtoken.cfg', 'r')
        self.apiauthkey = authfile.read()
        authfile.close()
        configfile = open('config.json', 'r')
        cdata = json.load(configfile)
        configfile.close()

        self.api_endpoint = cdata['api_endpoint']
        self.database_location = cdata['database_location']
        self.order_message = cdata['order_message']
        self.orders_open = cdata['orders_open']
        self.sticker_count = cdata['sticker_count']
        self.multi_select_count = cdata['multi_select_count']
        self.radio_select_count = cdata['radio_select_count']
        self.schedule_tolerance = cdata['schedule_tolerance']
        self.ss_hours = cdata['ss_hours']
        self.cherrypy = cdata['cherrypy']
        self.cherrypy['/']['tools.staticdir.root'] = os.path.abspath(os.getcwd())


cfg = Config()


class Uberconfig:
    """
    Class to make relevant config data from Uber easily accessible
    """

    # runs API request
    REQUEST_HEADERS = {'X-Auth-Token': cfg.apiauthkey}
    # data being sent to API
    request_data = {'method': 'config.info'}
    request = requests.post(url=cfg.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
    response = json.loads(request.text)

    try:
        response = response['error']
        # print(response)
    except KeyError:
        response = response['result']
        # print(response)
        EVENT_NAME = response['EVENT_NAME']
        EVENT_URL_ROOT = response['URL_ROOT']


c = Uberconfig()

env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=True,
        lstrip_blocks=True,
        trim_blocks=True
    )

dec_base = declarative_base()

