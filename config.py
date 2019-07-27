import json
import requests

from jinja2 import Environment, FileSystemLoader

#todo: add configs for settings related to min time for eligibility
class Config():
    """
    Class to make config data easily accessible
    """

    #read in config from files.  todo: option to load other config files than default
    authfile = open('authtoken.cfg', 'r')
    apiauthkey = authfile.read()  # api key for Uber todo: better way to handle this
    authfile.close()
    configfile = open('config.json', 'r')
    cdata = json.load(configfile)
    configfile.close()


    api_endpoint = cdata['api_endpoint']
    database_location = cdata['database_location']
    order_message = cdata['order_message']
    orders_open = cdata['orders_open']
    sticker_count = cdata['sticker_count']
    cherrypy = cdata['cherrypy']



class Uberconfig():
    """
    Class to make relevant config data from Uber easily accessible
    """
    c = Config()

    # runs API request
    REQUEST_HEADERS = {'X-Auth-Token': c.apiauthkey}
    # data being sent to API
    request_data = {'method': 'config.info'}
    request = requests.post(url=c.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
    response = json.loads(request.text)

    error = 'no_error'  # todo: process actual error checking
    #todo add items to load usefuldata from response, or else remove this class

env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=True,
        lstrip_blocks=True,
        trim_blocks=True
    )