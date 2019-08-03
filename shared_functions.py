import json
import requests
from urllib.parse import quote, urlparse

import cherrypy

from config import cfg
from models import attendee


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

    error = '' #todo: process actual error checking
    #print(response)
    return response

def lookup_attendee(first_name, last_name, email, zip_code):
    """
    Performs login request again Uber API and returns an Attendee object
    This returns StaffSuiteOrdering Attendee object, not an Uber object
    """
    json = api_login(first_name, last_name, email, zip_code)
    if error:
        #todo: raise exception probably
        print('error in lookup_attendee')
    else:
        # todo: lookup attendee and return it
        att = attendee.Attendee()
        att.public_id = json['public_id']