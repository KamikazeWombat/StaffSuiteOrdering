import json

authfile = open('authtoken.cfg', 'r')
apiauthkey = authfile.read() #api key for Uber todo: better way to handle this
configfile = open('config.json', 'r')
config = json.load(configfile)

print(config['orders_open'])
