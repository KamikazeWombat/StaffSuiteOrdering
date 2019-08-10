#sections of this are copied from https://github.com/magfest/ubersystem/blob/master/uber/site_sections/signups.py
#then modified for my needs.
import datetime
from dateutil.parser import parse

import cherrypy
import sqlalchemy.orm.exc
from sqlalchemy.orm import Session

from config import env, cfg, c
from decorators import restricted
import models
from models.attendee import Attendee
from models.meal import Meal
from models.order import Order
import shared_functions
from shared_functions import api_login, HTTPRedirect, order_split, order_join, meal_join


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

            if 'error' in response:
                message = response['error']['message']

            if not message:
                #ensure_csrf_token_exists()
                cherrypy.session['staffer_id'] = response['result']['public_id']
                raise HTTPRedirect(original_location)

        return template.render(message=message,
                               first_name=first_name,
                               last_name=last_name,
                               email=email,
                               zip_code=zip_code,
                               original_location=original_location,
                               c=c)

    @cherrypy.expose
    #@restricted
    #@admin_req todo: setup admin_req for requiring admin access
    def meal_setup_list(self, message='', id=''):
        template = env.get_template('meal_setup_list.html')
        session = Session(models.engine)

        #this should be triggered if an edit button is clicked from the list
        if id:
            raise HTTPRedirect('meal_edit?meal_id='+id)

        meallist = session.query(Meal).all()
        return template.render(message=message,
                               meallist=meallist,
                               c=c)

    @cherrypy.expose
    #@admin_req
    def meal_edit(self, options=[], toppings=[], meal_id='', message='', **params):
        template = env.get_template("meal_edit.html")

        if 'meal_name' in params:
            session = Session(models.engine)
            thismeal = Meal()
            print('----------------------')
           # for param in params:
            #    print(param)
             #   print(type(param))
            thismeal.meal_name = params['meal_name']
            thismeal.start_time = parse(params['start_time'])
            thismeal.end_time = parse(params['end_time'])
            thismeal.cutoff = parse(params['cutoff'])
            thismeal.description = params['description']
            thismeal.toppings = meal_join(session, params, field='toppings')
            #thismeal.detail_link = params['detail_link']

            session.add(thismeal)
            session.commit()
            session.close()
            raise HTTPRedirect('meal_setup_list?message=Meal succesfully added!')

        if meal_id:
            try:
                session = Session(models.engine)
                thismeal = session.query(Meal).filter_by(id=meal_id).one()
            except sqlalchemy.orm.exc.NoResultFound:
                message = 'Requested Meal ID '+meal_id+' not found'
                raise HTTPRedirect('meal_setup_list?message='+message)
            finally:
                session.close()

            toppings = thismeal.toppings.split(',')
            return template.render(meal=thismeal,
                                   toppings=toppings,
                                   message=message,
                                   c=c)
        else:
            thismeal = Meal()
            thismeal.meal_name = ''
            thismeal.description = ''
            thismeal.toppings_title = ''
            #make blank boxes for new meal.  todo: make number configurable
            toppings = [('','',''),('','',''),('','','')]
            return template.render(meal=thismeal,
                                   toppings=toppings,
                                   message=message,
                                   c=c)
