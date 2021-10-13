import copy
import json
import random
import requests
from urllib.parse import quote, urlparse
import uuid

import cherrypy
from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal
import pytz
import sqlalchemy.orm.exc

from config import cfg, c
import models
from models.ingredient import Ingredient
from models.department import Department


class HTTPRedirect(cherrypy.HTTPRedirect):
    #copied from https://github.com/magfest/ubersystem/blob/132143b385442677cb08178e16f714180ad75413/uber/errors.py
    """
    CherryPy uses exceptions to indicate things like HTTP 303 redirects.
    This subclasses the standard CherryPy exception to add string formatting
    and automatic quoting.  So instead of saying::
        raise HTTPRedirect('foo?message={}'.format(quote(bar)))
    we can say::
        raise HTTPRedirect('foo?message={}', bar)
    EXTREMELY IMPORTANT: If you pass in a relative URL, this class will use
    the current querystring to build an absolute URL.  Therefore it's
    EXTREMELY IMPORTANT that the only time you create this class is in the
    context of a pageload.
    Do not save copies this class, only create it on-demand when needed as
    part of a 'raise' statement.
    """
    def __init__(self, page, *args, **kwargs):
        save_location = kwargs.pop('save_location', False)

        args = [self.quote(s) for s in args]
        kwargs = {k: self.quote(v) for k, v in kwargs.items()}
        query = page.format(*args, **kwargs)

        if save_location and cherrypy.request.method == 'GET':
            # Remember the original URI the user was trying to reach.
            # useful if we want to redirect the user back to the same
            # page after they complete an action, such as logging in
            # example URI: '/uber/registration/form?id=786534'
            original_location = cherrypy.request.wsgi_environ['REQUEST_URI']

            # Note: python does have utility functions for this. if this
            # gets any more complex, use the urllib module
            qs_char = '?' if '?' not in query else '&'
            query += '{sep}original_location={loc}'.format(
                sep=qs_char, loc=self.quote(original_location))

        cherrypy.HTTPRedirect.__init__(self, query)

    def quote(self, s):
        return quote(s) if isinstance(s, str) else str(s)


def create_valid_user_supplied_redirect_url(url, default_url):
    #copied from https://github.com/magfest/ubersystem/blob/e7e9a7ae21097d5db7519d1c985b68feec328d21/uber/utils.py#L177
    """
    Create a valid redirect from user-supplied data.
    If there is invalid data, or a security issue is detected, then
    ignore and redirect to the homepage.
    Ignores cross-site redirects that aren't for local pages, i.e. if
    an attacker passes in something like:
    "original_location=https://badsite.com/stuff/".
     Args:
        url (str): User-supplied URL that is requested as a redirect.
        default_url (str): The URL we should use if there's an issue
            with `url`.
    Returns:
        str: A secure and valid URL that we allow for redirects.
    """
    parsed_url = urlparse(url)
    security_issue = parsed_url.scheme or parsed_url.netloc

    if not url or 'login' in url or security_issue:
        return default_url

    return url


def parse_utc(date):
    """
    takes datetime string and makes it a datetime object with timezone UTC
    :param date: string date
    :return: datetime object with tzinfo set to UTC
    """
    date = parse(date)
    date = pytz.utc.localize(date)
    return date


def utc_tz(date):
    """converts a datetime object OR a date string from event local to UTC TZ datetime object for storage"""
    if isinstance(date, str):
        date = parse(date)
    
    try:
        date = c.EVENT_TIMEZONE.localize(date)
    except ValueError:
        pass  # would happen if already has tzinfo
    
    date = date.astimezone(pytz.utc)
    return date


def con_tz(date):
    """converts a datetime object OR a date string from UTC to local TZ datetime object for display"""
    if isinstance(date, str):
        date = parse_utc(date)
        
    try:
        date = pytz.utc.localize(date)
    except ValueError:
        pass  # would happen if already has tzinfo
    
    date = date.astimezone(c.EVENT_TIMEZONE)
    date = date.replace(tzinfo=None)
    return date


def now_utc():
    """returns the current datetime now, converted to UTC beforehand, without TZ info"""
    now = datetime.now()
    now = now.replace(tzinfo=tzlocal())  # sets timezone info to server local TZ
    now = now.astimezone(pytz.utc)  # converts time from local TZ to UTC
    now = now.replace(tzinfo=None)  # removes tzinfo to avoid confusing other systems
    return now


def now_contz():
    """returns the current datetime now, converted to Con local TZ beforehand, without TZ info"""
    now = datetime.now()
    now = now.replace(tzinfo=tzlocal())  # sets timezone info to server local TZ
    now = now.astimezone(c.EVENT_TIMEZONE)  # converts time from local TZ to UTC
    now = now.replace(tzinfo=None)  # removes tzinfo to avoid confusing other systems
    return now


def api_login(first_name, last_name, email, zip_code):
    """
    Performs login request against Uber API and returns resulting json data
    """

    REQUEST_HEADERS = {'X-Auth-Token': cfg.uber_authkey}
    request_data = {'method': 'attendee.login',
                    'params': [first_name.strip(), last_name.strip(), email.strip(), zip_code.strip()]}
    request = requests.post(url=cfg.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
    response = json.loads(request.text)

    return response


def barcode_to_badge(barcode):
    """
    Queries uber to get the badge number associated with a barcode
    """
    REQUEST_HEADERS = {'X-Auth-Token': cfg.uber_authkey}
    request_data = {'method': 'barcode.lookup_badge_number_from_barcode',
                    'params': [barcode,]}
    request = requests.post(url=cfg.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
    response = json.loads(request.text)
    if "error" in response:
        return None
    return response['result']['badge_num']


def add_access(badge, usertype=None):
    """
    Adds provided badge number (or barcode) to selected access list
    :param badge:
    :param usertype: 'admin' or 'staff' or 'food_manager'
    :return:
    """
    if badge[0] == "~":
        badge = barcode_to_badge(badge)
    else:
        try:
            badge = int(badge)
        except ValueError:
            raise HTTPRedirect("Not a number?")

    if not badge:
        raise HTTPRedirect("config?message=Badge not found")

    session = models.new_sesh()
   
    try:
        attend = session.query(models.attendee.Attendee).filter_by(badge_num=badge).one()
    except sqlalchemy.orm.exc.NoResultFound:
        response = lookup_attendee(badge)
        if 'error' in response:
            session.close()
            # admin or staff would be added using config page, Food Manager would be from dept_orders page
            if usertype == 'admin' or usertype == 'staff':
                raise HTTPRedirect("config?message=Badge " + str(badge) + " is not found in Reggie")
            else:
                raise HTTPRedirect("dept_order_selection?message=Badge " + str(badge) + "is not found in Reggie")
        
        attend = models.attendee.Attendee()
        attend.badge_num = response['result']['badge_num']
        attend.public_id = response['result']['public_id']
        attend.full_name = response['result']['full_name']
        session.add(attend)
        session.commit()

    if usertype == 'admin' and attend.public_id not in cfg.admin_list:
        cfg.admin_list.append(attend.public_id)
    if usertype == 'staff' and attend.public_id not in cfg.staffer_list:
        cfg.staffer_list.append(attend.public_id)
    if usertype == 'food_manager' and attend.public_id not in cfg.food_managers:
        if is_dh(attend.public_id):
            session.close()
            raise HTTPRedirect("dept_order_selection?message=Badge " + str(badge) + "is already a Department Head")
        if is_admin(attend.public_id):
            session.close()
            raise HTTPRedirect("dept_order_selection?message=Badge " + str(badge) + "is already a Tuber Eats Admin")

        cfg.food_managers.append(attend.public_id)
        manager_list = ',\n'.join(cfg.food_managers)
        managerfile = open('food_managers.cfg', 'w')
        managerfile.write(manager_list)
        managerfile.close()
        session.close()
        return True
        
    session.close()
    return False


def load_departments():
    """
    Loads departments from connected Uber instance
    :return:
    """
    REQUEST_HEADERS = {'X-Auth-Token': cfg.uber_authkey}

    request_data = {'method': 'dept.list'}
    request = requests.post(url=cfg.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
    response = json.loads(request.text)
    response = response['result'].items()

    session = models.new_sesh()
    for dept in response:
        try:
            mydept = session.query(Department).filter_by(id=dept[0]).one()
            if not mydept.name == dept[1]:
                mydept.name = dept[1]
        except sqlalchemy.orm.exc.NoResultFound:
            mydept = Department()
            mydept.id = dept[0]
            mydept.name = dept[1]
            session.add(mydept)
            
    session.commit()
    session.close()
    return
    

def lookup_attendee(badge_num, full=False):
    """
    Looks up an existing attendee by badge_num and returns the resulting json data
    """
    REQUEST_HEADERS = {'X-Auth-Token': cfg.uber_authkey}

    if full:
        request_data = {'method': 'attendee.lookup',
                        'params': [badge_num, True]}
    else:
        request_data = {'method': 'attendee.lookup',
                        'params': [badge_num]}
        
    request = requests.post(url=cfg.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
    response = json.loads(request.text)

    return response


def order_split(session, choices, orders=""):
    """
    Creates tuple from list of ingredient IDs in format needed for display on order screens
    :param session: SQLAlchemny session passed from above
    :param orders: list of ingredient IDs that were chosen in order
    :param choices: list of ingredient IDs that are available
    :return: list of tuple(checked, label, description)
    """
    try:
        choices_list = sorted(choices.split(','))
    except ValueError:
        # this happens if no toppings in list
        return []
    
    choices_list = session.query(Ingredient).filter(Ingredient.id.in_(choices_list)).all()
    tuple_list = []
    
    if orders:
        orders_id = sorted(orders.split(','))
        orders_list = session.query(Ingredient).filter(Ingredient.id.in_(orders_id)).all()
    else:
        orders_list = []
    
    for choice in choices_list:
        if choice in orders_list:
            mytuple = (1, choice.label, choice.description, choice.id)
        else:
            mytuple = ('', choice.label, choice.description, choice.id)
            
        tuple_list.append(mytuple)
    
    return tuple_list


def return_selected_only(session, choices, orders):
    """
    Runs order_split and only returns the items that were actually selected
    """
    mylist = order_split(session, choices, orders)
    selected = list()
    for item in mylist:
        if item[0] == 1:
            selected.append(item)
    
    return selected


def return_not_selected(session, choices, orders):
    """
    Runs order_split and only returns the items that were not selected
    Used for label printing of toppings, where it was decided that showing what people don't want is easier
    """
    mylist = order_split(session, choices, orders)
    selected = list()
    for item in mylist:

        if not item[0] == 1:

            selected.append(item)

    return selected


def order_selections(field, params, is_toggle=False):
    """
    Takes field name and list of ingredient choice IDs and goes through params to find which of the available choices
    was actually selected
    :param field: name of the field it should check for in params
    :param params: web page submitted parameter list
    :return: result is a string which contains a comma separated list of selected ingredient IDs
    """
    
    result = []
    count = 1
    
    if is_toggle:
        try:
            return params[field]
        except KeyError:
            return ''
    
    for param in params:
        valuekey = field + str(count)
        # checks for relevant parameters and does stuff if found
        try:
            value = params[valuekey]
            
            if not value == '' and not value == 'None' and not value == 0:
                # then field is checked so loads id into result
                idkey = field + 'id' + str(count)
                id = params[idkey]
                result.append(str(id))
            count += 1
        except KeyError:
            count += 1
    
    result = ','.join(result)
    
    return result


def meal_join(session, params, field):
    """
    Goes through parameters and finds ingredients based upon which form field it is asked to look for.
    Adds new ingredients if not in DB, loads then updates ingredients if they are already existing in DB
    :param session: SQLAlchemy session
    :param params: web form parameters submitted
    :param field: string name of form field to look for
    :return: result is a string containing a comma separated list of ingredient IDs
    """
    result = []
    count = 1
    fieldid = ''

    for param in params:
        labelkey = field + str(count)
        new_ing = False
        # checks for relevant parameters and does stuff if found
        try:
            label = params[labelkey]
            if not label == '':
                try:
                    idkey = field + 'id' + str(count)
                    fieldid = params[idkey]
                except KeyError:
                    # marks this as a new ingredient if ID field is missing for this field number
                    new_ing = True
                    
                # if the field is there sets contents, otherwise blank
                try:
                    desc = field + 'desc' + str(count)
                    desc = params[desc]
                except KeyError:
                    desc = ''
    
                if new_ing or fieldid == '':
                    ing = Ingredient()
                    ing.label = label
                    ing.description = desc
                    session.add(ing)
                    session.commit()
                    # saves ing to DB so it gets an id, then puts result where it can be returned
                    fieldid = ing.id
                else:
                    # if not a new ingredient, but the label and description are both blank
                    # then it is one that was deleted from the meal.  do not load from DB, do not add to result.
                    if label == '' and desc == '':
                        count += 1
                        break

                    ing = session.query(Ingredient).filter_by(id=fieldid).one()
                    # if changed saves to DB
                    if not (ing.label == label and ing.description == desc):
                        ing.label = label
                        ing.description = desc
                        session.commit()
                
                result.append(str(fieldid))
            count += 1
        except KeyError:
            count += 1

    result = ','.join(result)
    return result


def meal_split(session, toppings):
    """
    Creates tuple from list of ingredient IDs in format needed for display on meal screens
    :param session: SQLAlchemny session passed from above
    :param toppings: list of ingredient IDs
    :return:
    """
    
    try:
        id_list = sorted(toppings.split(','))
    except ValueError:
        # this happens if no toppings in list
        return []
    
    ing_list = session.query(Ingredient).filter(Ingredient.id.in_(id_list)).all()
    tuple_list = []
    for ing in ing_list:
        mytuple = (ing.id, ing.label, ing.description)
        tuple_list.append(mytuple)
        
    return tuple_list


def meal_blank_toppings(toppings, count):
    """
    Adds blank toppings to end of list to make added spaces when editing
    :param toppings: list of tuples in format needed for display on meal screens
    :param count: How many lines do you want
    """
    
    while len(toppings) < count:
        toppings.append(('', '', ''))
        
    return toppings


def department_split(session, default=""):
    """
    Creates list of tuples of all departments
    :param session: SQLAlchemy session
    :param default: Optional, which department should be selected by default
    :return: sorted list of tuples of departments
    """
    result = [('', '', '')]
    departments = session.query(Department).all()
    
    for dept in departments:
        if dept.id == default:
            result.append((dept.name, dept.id, True))
        else:
            result.append((dept.name, dept.id, False))
    
    def dept_sort(dept_tuple):
        # lets sorting be case insensitive
        return dept_tuple[0].casefold()
    
    return sorted(result, key=dept_sort)


class Shift:
    """
    Contains relevant info for a shift needed to do eligibility calculations.
    Times are python dateutil objects, optional weight is whatever the shift is weighted for
    """

    def __init__(self, start_time, end_time, extra_15=False):
        self.start = start_time
        self.extra_15 = extra_15
        if extra_15:
            self.end = end_time + relativedelta(minutes=15)
        else:
            self.end = end_time
    
    @property
    def length(self):
        return relativedelta(self.end, self.start)
    
    def __lt__(self, other):
        return self.start < other.start
       

def ss_eligible(badge_num):
    """
    Looks up attendee badge number in Uber and returns whether they are eligible to use Staff Suite.
    General eligiblity to get food, not eligiblity for any specific meal
    :param badge_num: attendee's badge number for lookup
    :return: returns True or False
    """
    
    response = lookup_attendee(badge_num, full=True)
    
    if "error" in response:
        print('------------Error looking up attendee eligibility for ' + badge_num + ' --------------')
        return False
    
    attendee = response['result']
    
    # people who signed up for no shifts but have worked required hours for eligibility
    if attendee['worked_hours'] >= cfg.ss_hours:
        return True
    # non-staff who are signed up for at least <current year's hours req> and have worked at least one shift
    if attendee['badge_type_label'] == "Attendee":
        if attendee['weighted_hours'] >= cfg.ss_hours:
            if attendee['worked_hours'] > 0:
                return True
    # Guests and Contractors automatically get access
    if attendee['badge_type_label'] in ["Guest", "Contractor"]:
        return True
    # shiftless departments are exempt from eligibility requirements
    for dept in attendee['assigned_depts_labels']:
        if dept in cfg.exempt_depts:
            return True
    # Department Heads always get access
    if response['result']['is_dept_head']:
        return True
    # Staff who have signed up for at least <event required> hours.
    # Having already worked a shift this event not required for people with Staff status
    if attendee['badge_type_label'] == "Staff":
        if attendee["weighted_hours"] >= cfg.ss_hours:
            return True
    # if nothing above matches, not eligible.
    return False


def combine_shifts(badge_num, full=False, no_combine=False):
    """
    Takes badge number and performs lookup against Uber API
    Gets list of shifts, sorts it, then combines any that are close together based on settings for allowable gaps
    :param badge_num: Staffer's badge number
    :param full: whether or not to also return entire response
    :param no_combine: skips combining shifts and merely returns unsorted shifts
    :return: returns sorted and merged list of shifts
    """
    
    response = lookup_attendee(badge_num, full=True)
    shift_list = []

    if 'error' in response:
        message = response['error']['message']
        print(message)
    else:
        shifts = response['result']['shifts']
        for shift in shifts:
            item = Shift(parse(shift['job']['start_time']),
                         parse(shift['job']['end_time']),
                         extra_15=shift['job']['extra15']
                         )
            shift_list.append(item)
            
    if no_combine:
        if full:
            return shift_list, response
        else:
            return shift_list
        
    shifts = sorted(shift_list)
    
    # combining loop doesn't like if there are no shifts for the selected attendee
    if len(shifts) == 0:
        if full:
            return [], response
        else:
            return []
        
    combined = []
    i = 0
    shift_buffer = relativedelta(minutes=cfg.schedule_tolerance)
    
    while i < (len(shifts) - 1):
        # want to know if the end of the first shift touches or is after the next shift (+ buffers)
        delta = relativedelta(shifts[i].end + shift_buffer, shifts[i+1].start)
        # rd is positive if first item is after second.  delta.days will be nonzero if shifts more than 24 hours apart
        if (delta.minutes >= 0 or delta.hours >= 0) and delta.days == 0:
            # print("combining shift")
            combined.append(Shift(shifts[i].start, shifts[i+1].end))
            i += 1
        else:
            # print("shift left unchanged")
            combined.append(shifts[i])
            i += 1
            if i == (len(shifts)-1):
                combined.append(shifts[i])  # adds last shift if last pair not being merged

    if full:
        return combined, response
    else:
        return combined


def carryout_eligible(shifts, meal_start, meal_end):
    """
    Takes a list of shifts and checks if they overlap the given meal period
    Uses rules for allowable gaps configured in system
    :param shifts: List of shift objects. Concurrent shifts must already be merged or this will not work correctly!
    :param meal_start : date object for the meal start in python dateutil datetime format
    :param meal_end : date object for the meal end in python dateutil datetime format
    :return: returns True or False
    """
    # need to check combined if shift starts within <<buffer>> after start of meal time or earlier
    # AND ends within <<buffer>exc> before end of meal time or later
    
    # if there are no shifts, skip processing
    if len(shifts) == 0:
        return False
    """code section for buffer, commented out cause not using buffer for Super 2020
    meal_buffer = relativedelta(minutes=cfg.schedule_tolerance)
    # print("Meal start: {} Meal End {}".format(str(meal_start),str(meal_end)))
    
    for shift in shifts:
        # print("shift start : {} Shift end: {}".format(str(shift.start),str(shift.end)))
        sdelta = relativedelta((meal_start + meal_buffer), shift.start)
        start_delta = sdelta.minutes + (sdelta.hours * 60)
        
        edelta = relativedelta(shift.end, (meal_end - meal_buffer))
        end_delta = edelta.minutes + (edelta.hours * 60)
        
        if start_delta >= 0 and end_delta >= 0 and sdelta.days == 0:
            # start_delta.days being anything other than 0 means the shift is more than 24 hours from the meal
            return True
    """
    # rd positive if first after second
    # ss=shift start, se = shift end.  ms=meal start, me= meal end
    # if ss after ms AND before me then good
    # if se after ms AND before me then good
    # if ss before ms AND se after me then good
    # if the shift is more than a day before or after the meal days != 0
    for shift in shifts:
        ss_ms = relativedelta(meal_start, shift.start)
        ss_ms_delta = ss_ms.minutes + (ss_ms.hours * 60)
        ss_me = relativedelta(meal_end, shift.start)
        ss_me_delta = ss_me.minutes + (ss_me.hours * 60)
        if ss_ms_delta <= 0 and ss_me_delta >= 0 and ss_ms.days == 0:
            # print('ss after ms AND before me then good')
            return True

        se_ms = relativedelta(meal_start, shift.end)
        se_ms_delta = se_ms.minutes + (se_ms.hours * 60)
        se_me = relativedelta(meal_end, shift.end)
        se_me_delta = se_me.minutes + (se_me.hours * 60)
        if se_ms_delta <= 0 and se_me_delta >= 0 and ss_ms.days == 0:
            # print('se after ms AND before me then good')
            return True
        
        if ss_ms_delta >= 0 and se_me_delta <= 0 and ss_ms.days == 0:
            # print('if ss before ms AND se after me then good')
            return True

    # if none of the shifts match the meal period, return false.
    return False


def is_admin(staff_id):
    if staff_id in cfg.admin_list:
        return True
    else:
        return False


def is_ss_staffer(staff_id):
    if (staff_id in cfg.admin_list) or (staff_id in cfg.staffer_list):
        return True
    else:
        return False


def is_dh(staff_id):
    # queries Uber/Reggie to find out if attendee is marked as a DH
    REQUEST_HEADERS = {'X-Auth-Token': cfg.uber_authkey}
    request_data = {'method': 'attendee.search',
                    'params': [staff_id]}
    request = requests.post(url=cfg.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
    response = json.loads(request.text)
    return response['result'][0]['is_dept_head']


def allergy_info(badge_num):
    """
    Performs API request to Uber/Reggie and returns allergy info
    :param badge_num:
    :return:  returns tuple of allergy info, blank if none
    """
    response = lookup_attendee(badge_num, full=True)
    if response['result']['food_restrictions']:
        allergies = {'standard_labels': response['result']['food_restrictions']['standard_labels'],
                     'freeform': response['result']['food_restrictions']['freeform']}
    else:
        allergies = {'standard_labels': '', 'freeform': ''}

    return allergies


def create_dept_order(dept_id, meal_id, session):
    """
    creates a new dept_order to track bundle for given department's orders for specified meal time
    """
    dept = session.query(Department).filter_by(id=dept_id).one()
    dept_order = models.dept_order.DeptOrder()
    dept_order.dept_id = dept_id
    dept_order.meal_id = meal_id
    dept_order.slack_contact = dept.slack_contact
    dept_order.slack_channel = dept.slack_channel
    dept_order.other_contact = dept.other_contact
    dept_order.text_contact = dept.text_contact
    dept_order.email_contact = dept.email_contact
    
    session.add(dept_order)
    session.commit()
    dept_order = session.query(models.dept_order.DeptOrder).filter_by(dept_id=dept_id, meal_id=meal_id).one()
    return dept_order


def send_webhook(url, data):
    """
    Sends webhook request
    :param url:provided url for webhook
    :param data: JSON format data
    :return:
    """
    request = requests.post(url=url, json=json.loads(data))
    
    return request.text


def dummy_data(count, startorder):
    """
    create dummy data for testing
    :startorder: starting order is provided so some basic fields can be valid without having to be filled out.
    :return:
    """

    # do not want to create dummy data in live DB!!!
    print("-----------Tried to create dummy data but this server is marked as live!-----------")
    if not cfg.devenv:
        return

    session = models.new_sesh()
    count = int(count)
    depts = session.query(Department).all()
    meals = session.query(models.meal.Meal).all()
    
    i = 0
    while i < count:
        order = copy.deepcopy(startorder)
        
        attend = models.attendee.Attendee()
        attend.public_id = str(uuid.uuid4())
        session.add(attend)
        order.attendee_id = attend.public_id
        
        meal = random.choice(meals)
        order.meal_id = meal.id
        
        dept = random.choice(depts)
        order.department_id = dept.id
        
        session.add(order)
        i += 1
    
    session.commit()
    session.close()
    return


def load_contact_details(dept_order, dept, params):
    """
    If contact field is blank, use default configured for overall department instead.  Perhaps default is not blank.
    """
    if 'slack_channel' in params:
        dept_order.slack_channel = params['slack_channel']
    else:
        dept_order.slack_channel = dept.slack_channel
    if 'slack_contact' in params:
        dept_order.slack_contact = params['slack_contact']
    else:
        dept_order.slack_contact = dept.slack_contact
    if 'other_contact' in params:
        dept_order.other_contact = params['other_contact']
    else:
        dept_order.other_contact = dept.other_contact

    return dept_order


def get_session_info():
    session = {
        'is_dh': cherrypy.session['is_dh'],
        'is_admin': cherrypy.session['is_admin'],
        'is_ss_staffer': cherrypy.session['is_ss_staffer'],
        'is_food_manager': cherrypy.session['is_food_manager']
    }
    return session
