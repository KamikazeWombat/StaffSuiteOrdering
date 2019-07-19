import json


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



c = Config()