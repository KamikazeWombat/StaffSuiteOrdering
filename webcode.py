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
from shared_functions import api_login, HTTPRedirect, order_split, order_join
from shared_functions import meal_join, meal_split, meal_blank_toppings


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

        #save new / updated meal
        if 'meal_name' in params:
            session = Session(models.engine)
            print('-----------------')
            print('begin meal_name section')
            try:
                #tries to load id from params, if not there or blank does new empty meal
                id = params['id']
                print('loaded ID param: ', id)
                if not id == '' and not id == 'None':
                    thismeal = session.query(Meal).filter_by(id=id).one()
                    print('loaded existing meal: ', thismeal.id)
                else:
                    thismeal = Meal()
            except KeyError:
                thismeal = Meal()
           # print('----------------------')
           # for param in params:
            #    print(param)
             #   print(type(param))
            thismeal.meal_name = params['meal_name']
            thismeal.start_time = parse(params['start_time'])
            thismeal.end_time = parse(params['end_time'])
            thismeal.cutoff = parse(params['cutoff'])
            thismeal.description = params['description']
            thismeal.toppings_title = params['toppings_title']
            thismeal.toppings = meal_join(session, params, field='toppings')
            #thismeal.detail_link = params['detail_link']

            session.add(thismeal)
            session.commit()
            session.close()
            raise HTTPRedirect('meal_setup_list?message=Meal succesfully added!')

        if meal_id:
            print('------------------')
            print('beginning meal_id section')
            try:
                session = Session(models.engine)
                thismeal = session.query(Meal).filter_by(id=meal_id).one()
               # print(thismeal.meal_name)
                #print(thismeal.toppings)
                #print(type(thismeal.toppings))
                toppings = meal_blank_toppings(meal_split(session, thismeal.toppings), cfg.multi_select_count)
            except sqlalchemy.orm.exc.NoResultFound:
                message = 'Requested Meal ID '+meal_id+' not found'
                raise HTTPRedirect('meal_setup_list?message='+message)
            
            session.close()
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
            print('----------------------------------')
            print(cfg.multi_select_count)
            toppings = meal_blank_toppings([], cfg.multi_select_count)
            return template.render(meal=thismeal,
                                   toppings=toppings,
                                   message=message,
                                   c=c)
