import json
import requests
from urllib.parse import quote, urlparse

import cherrypy
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from config import cfg
import models
from models.attendee import Attendee
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


def api_login(first_name, last_name, email, zip_code):
    """
    Performs login request against Uber API and returns resulting json data
    """

    #runs API request
    REQUEST_HEADERS = {'X-Auth-Token': cfg.apiauthkey}
    # data being sent to API
    request_data = {'method': 'attendee.login',
                    'params': [first_name, last_name, email, zip_code]}
    request = requests.post(url=cfg.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
    response = json.loads(request.text)

    #print(response)
    return response


def load_departments(session):
    REQUEST_HEADERS = {'X-Auth-Token': cfg.apiauthkey}
    
    # data being sent to API
    request_data = {'method': 'dept.list'}
    
    request = requests.post(url=cfg.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
    response = json.loads(request.text)
    response = response['result'].items()
    session.query(Department).delete()
    session.commit()
    print('loading departments')
    for dept in response:
        mydept = Department()
        mydept.id = dept[0]
        mydept.name = dept[1]
        session.add(mydept)
    session.commit()
    return
    

def lookup_attendee(badge_num, full=False):
    """
    Looks up an existing attendee by badge_num and returns the resulting json data
    """
    REQUEST_HEADERS = {'X-Auth-Token': cfg.apiauthkey}
    
    # data being sent to API
    if full:
        request_data = {'method': 'attendee.lookup',
                        'params': [badge_num, full]}
    else:
        request_data = {'method': 'attendee.lookup',
                        'params': [badge_num]}
        
    request = requests.post(url=cfg.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
    response = json.loads(request.text)

    # print(response)
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
    selected = []
    for item in mylist:
        if item[0] == 1:
            selected.append(item)
    
    return selected


def order_selections(field, params):
    """
    Takes field name and list of ingredient choice IDs and goes through params to find which of the available choices
    was actually selected
    :param field: name of the field it should check for in params
    :param params: web page submitted parameter list
    :return: result is a string which contains a comma separated list of selected ingredient IDs
    """
    
    result = []
    count = 1
  
    for param in params:
        valuekey = field + str(count)
        # checks for relevant parameters and does stuff if found
        try:
            value = params[valuekey]
            
            if not value == '' and not value == 'None' and not value == 0:
                # if checked loads id into result
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
    Goes through paramaters and finds ingredients based upon which field it is asked to look for.
    Adds new ingredients if not in DB, loads then updates ingredients if they are already existing in DB
    :param session: SQLAlchemy session
    :param params: web form parameters submitted
    :param field: string name of field to look for
    :return: result is a string containing a comma separated list of ingredient IDs
    """
    result = []
    count = 1
    id=''

    for param in params:
        labelkey = field + str(count)
        new_ing = False
        # checks for relevant parameters and does stuff if found
        try:
            label = params[labelkey]
            if not label == '' and not label == 'None':
                try:
                    idkey = field + 'id' + str(count)
                    id = params[idkey]
                except KeyError:
                    # marks this as a new ingredient if ID field is missing for this field number
                    new_ing = True
                    
                # if the field is there sets contents, otherwise blank
                try:
                    desc = field + 'desc' + str(count)
                    desc = params[desc]
                except KeyError:
                    desc = ''
    
                if new_ing or id == '':
                    ing = Ingredient()
                    ing.label = label
                    ing.description = desc
                    session.add(ing)
                    session.commit()
                    # saves ing to DB so it gets an id, then puts result where it can be returned
                    id = ing.id
                else:
                    # if not a new ingredient, but the label and description are both blank
                    # then it is one that was deleted from the meal.  do not load from DB, do not add to result.
                    if label == '' and desc == '':
                        count += 1
                        break
                        
                    ing = session.query(Ingredient).filter_by(id=id).one()
                    # reduce unnecessary calls to DB
                    if not (ing.label == label and ing.description == desc):
                        ing.label = label
                        ing.description = desc
                        session.commit()
                
                result.append(str(id))
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
        #this happens if no toppings in list
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


def department_split(session, department=""):
    """
    Creates list of tuples of all departments
    :param session: SQLAlchemy session
    :return: sorted list of tuples of departments
    """
    result = [('', '', '')]
    departments = session.query(Department).all()
    
    for dept in departments:
        if dept.id == department:
            result.append((dept.name, dept.id, True))
        else:
            result.append((dept.name, dept.id, False))
    
    return sorted(result)


class Shift:
    """
    Contains relevant info for a shift needed to do eligibility calculations.
    Times are python dateutil objects, optional weight is whatever the shift is weighted for
    """
    #start_time = ''
    #end_time = ''
    #weight = ''
    
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
    Performs calculations to determine if eligible for StaffSuite and optionally returns a list of shift objects
    for the requested badge number
    :param badge_num: attendee's badge number for lookup
    :return: returns True or False, unless error performing the API Lookup in which case it returns the error
    """
    
    response = lookup_attendee(badge_num, full=True)
    message = ''
    
    if 'error' in response:
        message = response['error']['message']
        print(message)
        
    if not message:
        return response['result']['weighted_hours'] > cfg.ss_hours
    else:
        return message


def combine_shifts(badge_num):
    """
    Takes badge number and performs lookup against Uber API
    Gets list of shifts, sorts it, then combines any that are close together based on settings for allowable gaps
    :param badge_num: Staffer's badge number
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
        
    shifts = sorted(shift_list)
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
    # need to check combined if shift starts within <<buffer>> after start of meal time
    # AND ends within <<buffer>> before end of meal time
    # todo: make time zone localization, check if eligibility checking actually works
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
        
    # if none of the combined shifts match the meal period, return false.
    return False
