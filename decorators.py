import functools
from functools import wraps

import cherrypy

from shared_functions import HTTPRedirect, is_admin, is_ss_staffer, is_dh
from config import cfg


def restricted(func):
    """
    Requires user to be logged in to a valid account
    """
    @wraps(func)
    def logged_in(*args, **kwargs):
        # print('beginning restricted')
        try:
            # print('checking if staffer id is already assigned')
            staff_id = cherrypy.session['staffer_id']
            # print('staffer id already assigned')
        except KeyError:
            # print('Redirect to login page')
            raise HTTPRedirect('login', save_location=True)

        return func(*args, **kwargs)
    return logged_in


def admin_req(func):
    """
    Require user to be logged in and an admin; this is controlled currently by admin_list.cfg
    admin_list.cfg is a comma separated list of user's public ID from Uber/Reggie
    System clears whitespace so each ID can be on it's own line for simplicity
    """
    @wraps(func)
    def with_admin(*args, **kwargs):
        try:
            staff_id = cherrypy.session['staffer_id']
        except KeyError:
            raise HTTPRedirect('login?message=You+are+not+logged+in - admin page', save_location=True)
        
        if cherrypy.session['is_admin']:
            pass
        else:
            raise HTTPRedirect('staffer_meal_list?message=You are not admin, your id: ' + staff_id)

        return func(*args, **kwargs)
    return with_admin


def ss_staffer(func):
    """
    Require user to be logged in and a Staff Suite Staffer;
    This is controlled currently by ss_staffer_list.cfg.  Admin users are also automatically ss_staffer
    ss_staffer_list.cfg is a comma separated list of user's public ID from Uber/Reggie
    System clears whitespace so each ID can be on it's own line for simplicity
    """
    @wraps(func)
    def is_staffsuite_staffer(*args, **kwargs):
        try:
            staff_id = cherrypy.session['staffer_id']
        except KeyError:
            raise HTTPRedirect('login?message=You+are+not+logged+in - ss_staffer page', save_location=True)
    
        # admin are by default also ss_staffer
        if cherrypy.session['is_ss_staffer'] or cherrypy.session['is_admin']:
            pass
        else:
            raise HTTPRedirect('staffer_meal_list?message=You are not SS Staffer, your id: ' + staff_id)
    
        return func(*args, **kwargs)

    return is_staffsuite_staffer


def dh_or_admin(func):
    """
    Requires user to be logged in and either a Department Head or an Admin.
    Also now 'food manager' which is a non-DH person assigned to handle order related things
    Department Head status is determined at login by checking their account in Uber/Reggie
    """
    @wraps(func)
    def with_dh_admin(*args, **kwargs):
        # check if logged in
        try:
            staff_id = cherrypy.session['staffer_id']
        except KeyError:
            raise HTTPRedirect('login?message=You+are+not+logged+in - DH or admin page', save_location=True)
        allowed = False
        if cherrypy.session['is_dh'] or cherrypy.session['is_admin']:
            allowed = True
           
        if not allowed:
            raise HTTPRedirect('staffer_meal_list?message=You are not DH or admin, your id: ' + staff_id)
        
        return func(*args, **kwargs)
    
    return with_dh_admin


def dh_or_staffer(func):
    """
    Requires user to be logged in and either a SS Staffer or Department Head or an Admin.
    Department Head status is determined at login by checking their account in Uber/Reggie
    """
    @wraps(func)
    def with_dh_staffer(*args, **kwargs):
        # check if logged in
        try:
            staff_id = cherrypy.session['staffer_id']
        except KeyError:
            raise HTTPRedirect('login?message=You+are+not+logged+in - DH or Staffer page', save_location=True)
        allowed = False
        if cherrypy.session['is_dh'] or cherrypy.session['is_ss_staffer'] or cherrypy.session['is_admin']:
            allowed = True
        
        if not allowed:
            raise HTTPRedirect('staffer_meal_list?message=You are not DH or staffer or admin, your id: ' + staff_id)
        
        return func(*args, **kwargs)
    
    return with_dh_staffer
