import functools
from functools import wraps

import cherrypy

from shared_functions import HTTPRedirect

def restricted(func):
    @wraps(func)
    def with_restrictions(*args, **kwargs):
        print('beginning restricted')
        try:
            print('beginning try')
            staff_id = cherrypy.session['staffer_id']
            print('after try')
        except KeyError:
            print('KeyError started')
            raise HTTPRedirect('login?message=You+are+not+logged+in', save_location=True)

        return func(*args, **kwargs)
    return with_restrictions

def admin_req(func):
    @wraps(func)
    def with_admin(*args, **kwargs):
        try:
            admin_id = cherrypy.session['staff_id']
        except KeyError:
            raise HTTPRedirect('admin_required')
        #todo: make admin_required page that just says you need admin for this page

        return func(*args, **kwargs)
    return with_admin
