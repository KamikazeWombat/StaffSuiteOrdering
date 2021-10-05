import json
import os
import requests
from sys import argv

from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal
from jinja2 import Environment, FileSystemLoader
import pytz
from sqlalchemy.ext.declarative import declarative_base


class Config:
    """
    Class to make config data easily accessible
    """
    
    def load_user_lists(self):
        adminfile = open('admin_list.cfg', 'r')
        admins = adminfile.read()
        adminfile.close()
        admin_list = admins.split(',')
        self.admin_list = list()
        for admin in admin_list:
            admin = admin.strip()
            self.admin_list.append(admin)
    
        ssfile = open('ss_staffer_list.cfg', 'r')
        staffers = ssfile.read()
        ssfile.close()
        staffer_list = staffers.split(',')
        self.staffer_list = list()
        for staffer in staffer_list:
            staffer = staffer.strip()
            self.staffer_list.append(staffer)
            
        managerfile = open('food_managers.cfg', 'r')
        managers = managerfile.read()
        managerfile.close()
        manager_list = managers.split(',')
        self.food_managers = list()
        for manager in manager_list:
            manager = manager.strip()
            self.food_managers.append(manager)
        
        deptfile = open('eligibility_exempt_depts.cfg', 'r')
        depts = deptfile.read()
        deptfile.close()
        dept_list = depts.split(',')
        self.exempt_depts = list()
        for dept in dept_list:
            dept = dept.strip()
            self.exempt_depts.append(dept)
    
    def __init__(self):
        # read in config from files.  todo: have system skip things that are not yet defined.  in particular, API key
        
        for arg in argv:
            if arg == '-dev':
                filename = 'devconfig.json'
                self.devenv = True
                break
            elif arg == '-test':
                filename = 'testingserver.json'
                self.devenv = True
                break
            elif arg == '-prod':
                self.devenv = False
                filename = 'config.json'
            else:
                filename = 'invalid commandline args.  choices are -dev, -test, and -prod.'

            
        configfile = open(filename, 'r')
        cdata = json.load(configfile)
        configfile.close()
        
        self.admin_list = ''
        self.staffer_list = ''
        self.exempt_depts = ''
        self.food_managers = ''
        self.load_user_lists()
        
        self.api_endpoint = cdata['api_endpoint']
        self.uber_key_location = cdata['uber_key_location']
        self.slack_key_location = cdata['slack_key_location']
        self.database_location = cdata['database_location']
        self.local_print = int(cdata['local_print'])
        self.remote_print = int(cdata['remote_print'])
        self.multi_select_count = int(cdata['multi_select_count'])
        self.radio_select_count = int(cdata['radio_select_count'])
        self.schedule_tolerance = int(cdata['schedule_tolerance'])
        self.date_format = cdata['date_format']
        self.ss_hours = int(cdata['ss_hours'])
        self.cherrypy = cdata['cherrypy']
        self.cherrypy['/']['tools.staticdir.root'] = os.path.abspath(os.getcwd())
        print(self.uber_key_location)
        uber_authfile = open(self.uber_key_location, 'r')
        self.uber_authkey = uber_authfile.read()
        self.uber_authkey = self.uber_authkey.strip()
        uber_authfile.close()

        slack_authfile = open(self.slack_key_location, 'r')
        self.slack_authkey = slack_authfile.read()
        self.slack_authkey = self.slack_authkey.strip()
        slack_authfile.close()

    def orders_open(self):
        now = datetime.now()
        now = now.replace(tzinfo=tzlocal())  # sets timezone info to server local TZ
        now = now.astimezone(pytz.utc)  # converts time from local TZ to UTC
    
        rd = relativedelta(now, c.EPOCH)
        if rd.minutes >= 0 or rd.hours >= 0 or rd.days >= 0:
            return True
        else:
            return False
        
    def save(self, admin_list, staffer_list, exempt_depts, manager_list):
        cdata = {
            'api_endpoint': self.api_endpoint,
            'uber_key_location': self.uber_key_location,
            'slack_key_location': self.slack_key_location,
            'database_location': self.database_location,
            'local_print': self.local_print,
            'remote_print': self.remote_print,
            'multi_select_count': self.multi_select_count,
            'radio_select_count': self.radio_select_count,
            'schedule_tolerance': self.schedule_tolerance,
            'date_format': self.date_format,
            'ss_hours': self.ss_hours,
            'cherrypy': self.cherrypy
        }
        
        configfile = open('config.json', 'w')
        json.dump(cdata, configfile, indent=2)
        configfile.close()
        
        adminfile = open('admin_list.cfg', 'w')
        adminfile.write(admin_list)
        adminfile.close()
        
        stafferfile = open('ss_staffer_list.cfg', 'w')
        stafferfile.write(staffer_list)
        stafferfile.close()
        
        deptfile = open('exempt_depts.cfg', 'w')
        deptfile.write(exempt_depts)
        deptfile.close()
        
        managerfile = open('food_managers.cfg', 'w')
        managerfile.write(manager_list)
        managerfile.close()
        
        self.load_user_lists()
        return


cfg = Config()


class Uberconfig:
    """
    Class to make relevant config data from Uber easily accessible
    """
    def __init__(self):
        # runs API request
        REQUEST_HEADERS = {'X-Auth-Token': cfg.uber_authkey}
        # data being sent to API
        request_data = {'method': 'config.info'}
        request = requests.post(url=cfg.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
        # print("------printing request before json load")
        # print(request.text)
        response = json.loads(request.text)
        
        try:
            response = response['error']
            print("error in response")
            print(response)
        except KeyError:
            response = response['result']
            # print("no error in response")
            # print(response)
        
        self.EVENT_NAME = response['EVENT_NAME']
        self.EVENT_URL_ROOT = response['URL_ROOT']
        self.EVENT_TIMEZONE = pytz.timezone(response['EVENT_TIMEZONE'])
        self.EVENT_TZ = self.EVENT_TIMEZONE
        EPOCH = response['EPOCH']
        EPOCH = parse(EPOCH)
        EPOCH = self.EVENT_TIMEZONE.localize(EPOCH)
        self.EPOCH = EPOCH.astimezone(pytz.utc)


# Config info pulled from Uber
c = Uberconfig()

# environment used by Jinja
env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=True,
        lstrip_blocks=True,
        trim_blocks=True
    )
# shared base for database items
dec_base = declarative_base()
