#import sys
import requests
import json
#import re

API_ENDPOINT = "https://staging-reggie.magfest.org/jsonrpc/"
# https://staging-reggie.magfest.org/api/reference

#read in authentication toke from file instead of hardcoded.  security yall!
authfile = open('authtoken.cfg', 'r')
REQUEST_HEADERS = {'X-Auth-Token':authfile.read()}
#data being sent to API
request_data = {'method':'attendee.search',
               'params':['Test Developer','full']}
request = requests.post(url = API_ENDPOINT, json = request_data, headers = REQUEST_HEADERS)
response = json.loads(request.text)

#print(response)
#print('------------')
#print(type(response))
userlist = response['result']
user = userlist[0]
#print(user['ec_phone'])
#print(type(user))
if not len(userlist):
    print('no users found')

if len(userlist) > 1:
    print('more than one user found')

if len(userlist):
#    result = re.search(r'ec_phone\': \S+', userlist[])
    for entry in userlist:
        print(entry['ec_phone'])
        print('is staff:', entry['staffing'])

print(type(response['result'][0]))
print('--------------')
for line,data in response['result'][0].items():
    print(line,type(data),data)
#print('------------------')
#print(type(response['result'][0]['assigned_depts_labels']))

#test = testprint['result']
#print(type(test))
#for line in test:
#    print(line)
#    print('-----------')

#print(len(test))

