import sys
import requests

API_ENDPOINT = "https://staging-reggie.magfest.org/jsonrpc/"
API_KEY = "014ef08b-fa5e-438a-b89c-c7d6c6f7c43a"
REQUEST_HEADERS = {'X-Auth-Token':'014ef08b-fa5e-438a-b89c-c7d6c6f7c43a'}
#data being sent to API
request_data = {'method':'attendee.search',
               'params':['Test Developer']}
request = requests.post(url = API_ENDPOINT, json = request_data, headers = REQUEST_HEADERS)
print(request.text)