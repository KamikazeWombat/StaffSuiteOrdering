import functools
from functools import wraps

import cherrypy

from shared_functions import HTTPRedirect, is_admin, is_ss_staffer, is_dh


def restricted(func):
    @wraps(func)
    def logged_in(*args, **kwargs):
        #print('beginning restricted')
        try:
         #   print('checking if staffer id is already assigned')
            staff_id = cherrypy.session['staffer_id']
          #  print('staffer id already assigned')
        except KeyError:
           # print('Redirect to login page')
            raise HTTPRedirect('login?message=You+are+not+logged+in', save_location=True)

        return func(*args, **kwargs)
    return logged_in


def admin_req(func):
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
    @wraps(func)
    def is_staffsuite_staffer(*args, **kwargs):
        try:
            staff_id = cherrypy.session['staffer_id']
        except KeyError:
            raise HTTPRedirect('login?message=You+are+not+logged+in - ss_staffer page', save_location=True)
    
        if cherrypy.session['is_ss_staffer']:
            pass
        else:
            raise HTTPRedirect('staffer_meal_list?message=You are not SS Staffer, your id: ' + staff_id)
    
        return func(*args, **kwargs)

    return is_staffsuite_staffer


def dh_or_admin(func):
    @wraps(func)
    def with_admin(*args, **kwargs):
        # check if logged in
        try:
            staff_id = cherrypy.session['staffer_id']
        except KeyError:
            raise HTTPRedirect('login?message=You+are+not+logged+in - DH or admin page', save_location=True)
        allowed = False
        if cherrypy.session['is_dh']:
            allowed = True
        
        if cherrypy.session['is_admin']:
            allowed = True
        
        if not allowed:
            raise HTTPRedirect('staffer_meal_list?message=You are not DH or admin, your id: ' + staff_id)
        
        return func(*args, **kwargs)
    
    return with_admin