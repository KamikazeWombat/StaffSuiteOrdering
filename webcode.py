#sections of this are copied from https://github.com/magfest/ubersystem/blob/master/uber/site_sections/signups.py
#then modified for my needs.
import cherrypy


from config import env, c
from decorators import restricted
import shared_functions
from shared_functions import api_login, HTTPRedirect


class Root:
    @cherrypy.expose
    def index(self):
        #todo: add check for if mealorders open
        template = env.get_template('index.html')



        return template.render()

    @cherrypy.expose
    def login(self, message='', first_name='', last_name='',
              email='', zip_code='', original_location=None):
        original_location = shared_functions.create_valid_user_supplied_redirect_url(original_location, default_url='index')
        template = env.get_template('login.html')

        if first_name and last_name and email and zip_code:
            response = api_login(first_name=first_name, last_name=last_name,
                       email=email, zip_code=zip_code)
            try:
                message = response['error']['message']
            except KeyError:
                message = message #if error isn't in response, ignore KeyError

            if not message:
                #ensure_csrf_token_exists()
                cherrypy.session['staffer_id'] = response['result']['public_id']
                raise HTTPRedirect(original_location)

        return template.render(message=message,
            first_name=first_name,
            last_name=last_name,
            email=email,
            zip_code=zip_code,
            original_location=original_location, c=c
            )

    #@cherrypy.expose
    #def mealsetuplist(self):

    @cherrypy.expose
    @restricted
    def meal_setup(self):

        return