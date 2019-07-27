#sections of this are copied from https://github.com/magfest/ubersystem/blob/master/uber/site_sections/signups.py
# then modified for my needs.
import cherrypy

from config import env

def logged_in_volunteer(self):
    return self.attendee(cherrypy.session['staffer_id'])

class Root:
    @cherrypy.expose
    def index(self):
        #todo: add check for if mealorders open
        template = env.get_template('index.html')
        return template.render()
