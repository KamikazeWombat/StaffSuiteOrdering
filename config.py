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
        self.admin_list = list()
        try:
            adminfile = open('admin_list.cfg', 'r')
            admins = adminfile.read()
            adminfile.close()
            admin_list = admins.split(',')
            for admin in admin_list:
                admin = admin.strip()
                self.admin_list.append(admin)
        except FileNotFoundError:
            pass

        self.staffer_list = list()
        try:
            ssfile = open('ss_staffer_list.cfg', 'r')
            staffers = ssfile.read()
            ssfile.close()
            staffer_list = staffers.split(',')
            for staffer in staffer_list:
                staffer = staffer.strip()
                self.staffer_list.append(staffer)
        except FileNotFoundError:
            pass

        self.food_managers = list()
        try:
            managerfile = open('food_managers.cfg', 'r')
            managers = managerfile.read()
            managerfile.close()
            manager_list = managers.split(',')
            for manager in manager_list:
                manager = manager.strip()
                self.food_managers.append(manager)
        except FileNotFoundError:
            pass

        self.super_admins = list()
        try:
            sa_file = open('super_admins.cfg', 'r')
            sa = sa_file.read()
            sa_file.close()
            sa_list = sa.split(',')
            for super in sa_list:
                super = super.strip()
                self.super_admins.append(super)
                if super not in self.admin_list:
                    self.admin_list.append(super)
        except FileNotFoundError:
            pass

    def __init__(self):
        """
        Load in config files and API keys (if files exist)
        """
        i = 0
        self.env = False
        filename = False
        while i < len(argv):
            if argv[i] == '-dev':
                self.env = "dev"
            elif argv[i] == '-testing':
                self.env = "testing"
            elif argv[i] == '-prod':
                self.env = "prod"
            elif argv[i] == '-config':
                i += 1
                filename = argv[i]
                self.config_file_in_use = filename
                print(filename)
            i += 1

        if not self.env or not filename:
            filename = 'Invalid commandline args.  Mode choices are -dev, -testing, and -prod.  ' \
                       'Must specify config file, ie -config devconfig.json'
            
        configfile = open(filename, 'r')
        cdata = json.load(configfile)
        configfile.close()

        self.version = "1.2.6"  # code version
        if 'last_version_loaded' in cdata:
            self.last_version_loaded = cdata['last_version_loaded']
        else:
            self.last_version_loaded = self.version

        self.admin_list = ''
        self.staffer_list = ''
        self.food_managers = ''
        self.super_admins = ''
        self.load_user_lists()
        
        self.api_endpoint = cdata['api_endpoint']
        self.uber_key_location = cdata['uber_key_location']
        self.slack_key_location = cdata['slack_key_location']
        self.aws_key_location = cdata['aws_key_location']
        self.twilio_key_location = cdata['twilio_key_location']

        if 'db_config' in cdata:
            self.db_config = cdata['db_config']
        else:
            self.db_config = None
        self.local_print = int(cdata['local_print'])
        self.remote_print = int(cdata['remote_print'])
        self.multi_select_count = int(cdata['multi_select_count'])
        self.radio_select_count = int(cdata['radio_select_count'])
        self.schedule_tolerance = int(cdata['schedule_tolerance'])
        self.date_format = cdata['date_format']
        self.ss_hours = int(cdata['ss_hours'])
        if 'early_login_enabled' in cdata:
            self.early_login_enabled = cdata['early_login_enabled']
        else:
            self.early_login_enabled = False
        self.room_location = str(cdata['room_location'])
        self.location_url = str(cdata['location_url'])
        self.ss_url = str(cdata['ss_url'])
        self.is_linux = cdata['is_linux']

        self.cherrypy_global = cdata['cherrypy_global']
        self.cherrypy = cdata['cherrypy']
        self.cherrypy['/']['tools.staticdir.root'] = os.path.abspath(os.getcwd())

        self.slackapp = cdata['slackapp']

        # Uber auth key is needed for login, so no skipping if file does not exist.  Others can be added later
        uber_authfile = open(self.uber_key_location, 'r')
        self.uber_authkey = uber_authfile.read()
        self.uber_authkey = self.uber_authkey.strip()
        uber_authfile.close()

        self.log_conf = cdata['log_conf']

        try:
            slack_authfile = open(self.slack_key_location, 'r')
            slack_data = json.load(slack_authfile)
            self.slack_authkey = slack_data['token'].strip()
            self.slack_signing_secret = slack_data['signing_secret'].strip()
            slack_authfile.close()
        except FileNotFoundError:
            pass

        try:
            aws_authfile = open(self.aws_key_location, 'r')
            awsdata = json.load(aws_authfile)
            self.aws_authuser = awsdata['aws_user'].strip()
            self.aws_authkey = awsdata['aws_authkey'].strip()
            aws_authfile.close()
        except FileNotFoundError:
            pass

        try:
            twilio_authfile = open(self.twilio_key_location, 'r')
            twiliodata = json.load(twilio_authfile)
            self.twilio_account_sid = twiliodata['twilio_account_sid'].strip()
            self.twilio_authkey = twiliodata['twilio_authkey'].strip()
            self.twilio_authsecret = twiliodata['twilio_authsecret'].strip()
            self.twilio_sendfrom = twiliodata['twilio_sendfrom'].strip()
            twilio_authfile.close()
        except FileNotFoundError:
            pass

        return

    def orders_open(self):
        """
        Returns if orders open yet for attendees, based on official start time for event in Uber
        """
        if cfg.early_login_enabled:
            return True

        now = datetime.now()
        now = now.replace(tzinfo=tzlocal())  # sets timezone info to server local TZ
        now = now.astimezone(pytz.utc)  # converts time from local TZ to UTC
    
        rd = relativedelta(now, c.EPOCH)
        if rd.minutes >= 0 or rd.hours >= 0 or rd.days >= 0:
            return True
        else:
            return False
        
    def save(self, admin_list="", staffer_list="", manager_list="", cfgonly=False):
        cdata = {
            'last_version_loaded': self.last_version_loaded,
            'api_endpoint': self.api_endpoint,
            'uber_key_location': self.uber_key_location,
            'slack_key_location': self.slack_key_location,
            'aws_key_location': self.aws_key_location,
            'twilio_key_location': self.twilio_key_location,
            'db_config': self.db_config,
            'local_print': self.local_print,
            'remote_print': self.remote_print,
            'multi_select_count': self.multi_select_count,
            'radio_select_count': self.radio_select_count,
            'schedule_tolerance': self.schedule_tolerance,
            'date_format': self.date_format,
            'ss_hours': self.ss_hours,
            'early_login_enabled': self.early_login_enabled,
            'room_location': self.room_location,
            'location_url': self.location_url,
            'ss_url': self.ss_url,
            'is_linux': self.is_linux,
            'cherrypy_global': self.cherrypy_global,
            'cherrypy': self.cherrypy,
            'slackapp': self.slackapp,
            'log_conf': self.log_conf
        }
        
        configfile = open(self.config_file_in_use, 'w')
        json.dump(cdata, configfile, indent=2)
        configfile.close()
        if cfgonly:  # cfgonly indicates that we are not attempting to update user role lists
            return

        adminfile = open('admin_list.cfg', 'w')
        adminfile.write(admin_list)
        adminfile.close()
        
        stafferfile = open('ss_staffer_list.cfg', 'w')
        stafferfile.write(staffer_list)
        stafferfile.close()

        managerfile = open('food_managers.cfg', 'w')
        managerfile.write(manager_list)
        managerfile.close()
        
        self.load_user_lists()
        return


cfg = Config()


class Uberconfig:
    """
    Class to load relevant config data from Uber and make easily accessible
    """
    def __init__(self):
        REQUEST_HEADERS = {'X-Auth-Token': cfg.uber_authkey}
        request_data = {'method': 'config.info'}
        request = requests.post(url=cfg.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
        response = json.loads(request.text)
        if 'error' in response:
            print("----------Error loading config from Uber----------")
            print(response)

        response = response['result']
        self.EVENT_NAME = response['EVENT_NAME']
        self.EVENT_YEAR = response['EVENT_YEAR']
        self.EVENT_URL_ROOT = response['URL_ROOT']
        if response['EVENT_TIMEZONE'] == 'US/Eastern':
            self.EVENT_TIMEZONE = pytz.timezone('America/New_York')
        else:
            self.EVENT_TIMEZONE = pytz.timezone(response['EVENT_TIMEZONE'])
        self.EVENT_TZ = self.EVENT_TIMEZONE
        EPOCH = response['EPOCH']
        EPOCH = parse(EPOCH)
        EPOCH = self.EVENT_TIMEZONE.localize(EPOCH)
        # Uber returns EPOCH in local TZ for event, I want to store all dates as UTC
        self.EPOCH = EPOCH.astimezone(pytz.utc)


# Config info pulled from Uber
c = Uberconfig()

# environment setup used by Jinja
env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=True,
        lstrip_blocks=True,
        trim_blocks=True
    )

# shared base for database models
dec_base = declarative_base()
