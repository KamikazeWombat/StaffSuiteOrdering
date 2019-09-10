import functools
from functools import wraps

import cherrypy

from shared_functions import HTTPRedirect

def restricted(func):
    @wraps(func)
    def with_restrictions(*args, **kwargs):
        #print('beginning restricted')
        try:
         #   print('checking if staffer id is already assigned')
            staff_id = cherrypy.session['staffer_id']
          #  print('staffer id already assigned')
        except KeyError:
           # print('Redirect to login page')
            raise HTTPRedirect('login?message=You+are+not+logged+in', save_location=True)

        return func(*args, **kwargs)
    return with_restrictions


def admin_req(func):
    print(fix_admin_req_function_first)
    @wraps(func)
    def with_admin(*args, **kwargs):
        try:
            admin_id = cherrypy.session['staff_id']
        except KeyError:
            raise HTTPRedirect('admin_required')
        # todo: make admin_required page that just says you need admin for this page
        # todo: admin_req error page show public_id and tell user to give this to an existing admin for access

        return func(*args, **kwargs)
    return with_admin
