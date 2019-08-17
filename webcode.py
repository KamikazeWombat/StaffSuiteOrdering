# sections of this are copied from https://github.com/magfest/ubersystem/blob/master/uber/site_sections/signups.py
# then modified for my needs.
from dateutil.parser import parse

import cherrypy
import sqlalchemy.orm.exc

from config import env, cfg, c
from decorators import restricted
import models
from models.attendee import Attendee
from models.meal import Meal
from models.order import Order
import shared_functions
from shared_functions import api_login, HTTPRedirect, order_split, order_selections
from shared_functions import meal_join, meal_split, meal_blank_toppings, department_split


class Root:
    @cherrypy.expose
    def index(self, load_depts=False):
        #todo: add check for if mealorders open
        template = env.get_template('index.html')
        if load_depts:
            session = models.new_sesh()
            shared_functions.load_departments(session)
            session.close()
            
        return template.render()

    @cherrypy.expose
    def login(self, message='', first_name='', last_name='',
              email='', zip_code='', original_location=None, logout=False):
        original_location = shared_functions.create_valid_user_supplied_redirect_url(original_location, default_url='index')
        template = env.get_template('login.html')
        
        if logout:
            cherrypy.lib.sessions.expire()
        if first_name and last_name and email and zip_code:
            response = api_login(first_name=first_name, last_name=last_name,
                       email=email, zip_code=zip_code)

            if 'error' in response:
                message = response['error']['message']

            if not message:
                # ensure_csrf_token_exists()
                cherrypy.session['staffer_id'] = response['result']['public_id']
                session = models.new_sesh()
                
                # add or update attendee record in DB
                try:
                    attendee = session.query(Attendee).filter_by(public_id=response['result']['public_id']).one()
                    
                    # only update record if different
                    if not attendee.badge_printed_name == response['result']['badge_printed_name']:
                        attendee.badge_printed_name = response['result']['badge_printed_name']
                        session.commit()
                except sqlalchemy.orm.exc.NoResultFound:
                    attendee = Attendee()
                    attendee.public_id = response['result']['public_id']
                    attendee.badge_printed_name = response['result']['badge_printed_name']
                    session.add(attendee)
                    session.commit()
                    
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
        session = models.new_sesh()

        # this should be triggered if an edit button is clicked from the list
        if id:
            raise HTTPRedirect('meal_edit?meal_id='+id)

        meallist = session.query(Meal).all()
        session.close()
        return template.render(message=message,
                               meallist=meallist,
                               c=c)

    @cherrypy.expose
    #@admin_req
    def meal_edit(self, meal_id='', message='', **params):
        template = env.get_template("meal_edit.html")

        # save new / updated meal
        if 'meal_name' in params:
            session = models.new_sesh()
            try:
                # tries to load id from params, if not there or blank does new empty meal
                id = params['id']
                message = 'Meal succesfully updated!'
                if not id == '' and not id == 'None':
                    thismeal = session.query(Meal).filter_by(id=id).one()
                    message = 'Meal succesfully added!'
                else:
                    thismeal = Meal()
            except KeyError:
                thismeal = Meal()
           
            thismeal.meal_name = params['meal_name']
            thismeal.start_time = parse(params['start_time'])
            thismeal.end_time = parse(params['end_time'])
            thismeal.cutoff = parse(params['cutoff'])
            thismeal.description = params['description']
            thismeal.toppings_title = params['toppings_title']
            thismeal.toppings = meal_join(session, params, field='toppings')
            thismeal.toggle1_title = params['toggle1_title']
            thismeal.toggle1 = meal_join(session, params, field='toggle1')
            thismeal.toggle2_title = params['toggle2_title']
            thismeal.toggle2 = meal_join(session, params, field='toggle2')
            # thismeal.detail_link = params['detail_link']

            session.add(thismeal)
            session.commit()
            session.close()
            raise HTTPRedirect('meal_setup_list?message='+message)

        if meal_id:
            # load existing meal
            try:
                session = models.new_sesh()
                thismeal = session.query(Meal).filter_by(id=meal_id).one()
               
                # loads list of existing toppings, adds blank toppings to list up to configured #
                toppings = meal_blank_toppings(meal_split(session, thismeal.toppings), cfg.multi_select_count)
                toggles1 = meal_blank_toppings(meal_split(session, thismeal.toggle1), cfg.radio_select_count)
                toggles2 = meal_blank_toppings(meal_split(session, thismeal.toggle2), cfg.radio_select_count)
            except sqlalchemy.orm.exc.NoResultFound:
                message = 'Requested Meal ID '+meal_id+' not found'
                raise HTTPRedirect('meal_setup_list?message='+message)
            
            session.close()
        else:
            thismeal = Meal()
            thismeal.meal_name = ''
            thismeal.description = ''
            thismeal.toppings_title = ''
            thismeal.toggle1_title = ''
            thismeal.toggle2_title = ''
            # make blank boxes for new meal.
            toppings = meal_blank_toppings([], cfg.multi_select_count)
            toggles1 = meal_blank_toppings([], cfg.radio_select_count)
            toggles2 = meal_blank_toppings([], cfg.radio_select_count)
            
        return template.render(meal=thismeal,
                               toppings=toppings,
                               toggles1=toggles1,
                               toggles2=toggles2,
                               message=message,
                               c=c)


    #@restricted
    @cherrypy.expose
    def order_edit(self, meal_id='', save_order='', order_id='', message='', notes='', **params):
        template = env.get_template('order_edit.html')
        session = models.new_sesh()
        
        # parameter save_order should only be present if saving
        if save_order:
            print('start save_order')
            # todo: save it lol
            
            # thismeal = session.query(Meal).filter_by(id=save_order).one()
            if order_id:
                thisorder = session.query(Order).filter_by(id=order_id).one(())
            else:
                thisorder = Order()
            
            thisorder.attendee_id = cherrypy.session['staffer_id']
            thisorder.department_id = params['department'] #todo: department dropdown
            thisorder.meal_id = params['save_order']  # save order kinda wonky, it will be meal id
            # todo: do something with overridden field
            thisorder.toggle1 = order_selections(field='toggle1', params=params)
            thisorder.toggle2 = order_selections(field='toggle2', params=params)
            thisorder.toppings = order_selections(field='toppings', params=params)
            thisorder.notes = notes
            
            session.close()
            #todo: replace with redirect to user orders list
            raise HTTPRedirect('meal_setup_list?message=saved meal')
        
        if order_id:
            print('start order_id')
            # todo: load order
        if meal_id:
            print('start meal_id')
            # todo: new blank order based on meal_id
            thismeal = session.query(Meal).filter_by(id=meal_id).one()
            thisorder = Order()
            #thisorder.attendee_id = cherrypy.session['staffer_id']
            toppings = order_split(session, thismeal.toppings)
            toggles1 = order_split(session, thismeal.toggle1)
            toggles2 = order_split(session, thismeal.toggle2)
            departments = department_split(session)
            thisorder.notes = ''
            
        else:
            print('start no meal id')
            # todo: redirect to non-admin meal list
        
        session.close()
        return template.render(order=thisorder,
                               meal=thismeal,
                               toppings=toppings,
                               toggles1=toggles1,
                               toggles2=toggles2,
                               departments=departments,
                               message=message,
                               c=c)
