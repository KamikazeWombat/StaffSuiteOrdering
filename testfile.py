#import sys
import requests
import json

API_ENDPOINT = "https://staging-reggie.magfest.org/jsonrpc/"

#read in authentication toke from file instead of hardcoded.  security yall!
authfile = open('authtoken.cfg', 'r')
REQUEST_HEADERS = {'X-Auth-Token':authfile.read()}
#data being sent to API
request_data = {'method':'attendee.search',
               'params':['Test Developer']}
request = requests.post(url = API_ENDPOINT, json = request_data, headers = REQUEST_HEADERS)
#testprint = json.loads(request.text, sort_keys=True, indent=2)
print(request.text)