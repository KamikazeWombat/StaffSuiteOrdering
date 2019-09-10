# sections of this are copied from https://github.com/magfest/ubersystem/blob/master/uber/site_sections/signups.py
# then modified for my needs.
import json
import requests

import cherrypy
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
import sqlalchemy.orm.exc
from sqlalchemy.orm import joinedload

from config import env, cfg, c
from decorators import restricted
import models
from models.attendee import Attendee
from models.meal import Meal
from models.order import Order
import shared_functions
from shared_functions import api_login, HTTPRedirect, order_split, order_selections, \
                         meal_join, meal_split, meal_blank_toppings, department_split, \
                        ss_eligible, carryout_eligible, combine_shifts

#todo: department select dropdown needs to restrict based upon if a department's order is already being processed or has been.

class Root:
    
    @restricted
    @cherrypy.expose
    def index(self, load_depts=False):
        #todo: add check for if mealorders open
        template = env.get_template('index.html')
        if load_depts:
            session = models.new_sesh()
            shared_functions.load_departments(session)
            session.close()
            
        return template.render(c=c)

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
                # is staff?
                if not response['result']['staffing']:
                    message = 'You are not currently signed up as staff/volunteer.' \
                              'See below for information on how to volunteer.'

            if not message:
                # ensure_csrf_token_exists()
                cherrypy.session['staffer_id'] = response['result']['public_id']
                cherrypy.session['badge_num'] = response['result']['badge_num']
                session = models.new_sesh()
                
                # add or update attendee record in DB
                try:
                    attendee = session.query(Attendee).filter_by(public_id=response['result']['public_id']).one()
                    
                    # only update record if different
                    if not attendee.badge_printed_name == response['result']['badge_printed_name'] \
                            and not attendee.badge_num == response['result']['badge_num']:
                        attendee.badge_printed_name = response['result']['badge_printed_name']
                        attendee.badge_num = response['result']['badge_num']
                        session.commit()
                except sqlalchemy.orm.exc.NoResultFound:
                    attendee = Attendee()
                    attendee.badge_num = response['result']['badge_num']
                    attendee.public_id = response['result']['public_id']
                    attendee.badge_printed_name = response['result']['badge_printed_name']
                    session.add(attendee)
                    session.commit()
                    
                session.close()
                    
                raise HTTPRedirect(original_location)

        return template.render(message=message,
                               first_name=first_name,
                               last_name=last_name,
                               email=email,
                               zip_code=zip_code,
                               original_location=original_location,
                               c=c)

    @cherrypy.expose
    @restricted
    #@admin_req todo: setup admin_req for requiring admin access
    def meal_setup_list(self, message='', id=''):
        template = env.get_template('meal_setup_list.html')
        session = models.new_sesh()

        # this should be triggered if an edit button is clicked from the list
        if id:
            raise HTTPRedirect('meal_edit?meal_id='+id)

        meallist = session.query(Meal).order_by(models.meal.Meal.start_time).all()
        session.close()
        return template.render(message=message,
                               meallist=meallist,
                               c=c)

    @cherrypy.expose
    #@admin_req
    @restricted  # todo: code admin_req and remove restricted tag
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


    @restricted
    @cherrypy.expose
    def order_edit(self, meal_id='', save_order='', order_id='', message='', notes='', **params):
        template = env.get_template('order_edit.html')
        session = models.new_sesh()
        thisorder = ''
        thismeal = ''
        
        # parameter save_order should only be present if saving
        if save_order:
            print('start save_order')
            # : save it lol
            
            if order_id:
                thisorder = session.query(Order).filter_by(id=order_id).one()
            else:
                thisorder = Order()
            
            thisorder.attendee_id = cherrypy.session['staffer_id']
            thisorder.department_id = params['department']
            thisorder.meal_id = save_order  # save order kinda wonky, data will be meal id if 'Submit' is clicked
            # todo: do something with overridden field
            thisorder.toggle1 = order_selections(field='toggle1', params=params)
            thisorder.toggle2 = order_selections(field='toggle2', params=params)
            thisorder.toppings = order_selections(field='toppings', params=params)
            thisorder.notes = notes
            
            session.add(thisorder)
            session.commit()
            session.close()
            
            raise HTTPRedirect('staffer_order_list?message=saved order')
        
        if order_id:
            print('start order_id')
            # load order
            thisorder = session.query(Order).filter_by(id=order_id).one()
            thismeal = thisorder.meal  # session.query(Meal).filter_by(id=thisorder.meal_id).one()
            
            toppings = order_split(session, choices=thismeal.toppings, orders=thisorder.toppings)
            toggles1 = order_split(session, choices=thismeal.toggle1, orders=thisorder.toggle1)
            toggles2 = order_split(session, choices=thismeal.toggle2, orders=thisorder.toggle2)
            departments = department_split(session)
            message = 'Order ID {} loaded'.format(order_id)
            attend = session.query(Attendee).filter_by(public_id=cherrypy.session['staffer_id'])
            session.close()
            
            return template.render(order=thisorder,
                                   meal=thismeal,
                                   attendee=attend,
                                   toppings=toppings,
                                   toggles1=toggles1,
                                   toggles2=toggles2,
                                   departments=departments,
                                   message=message,
                                   c=c)
            
        if meal_id:
            print('start meal_id')
            # new blank order from meal_id
            # todo: check if attendee already has an order for this meal
            thismeal = session.query(Meal).filter_by(id=meal_id).one()
            thisorder = Order()
            thisorder.attendee_id = cherrypy.session['staffer_id']
            toppings = order_split(session, thismeal.toppings)
            toggles1 = order_split(session, thismeal.toggle1)
            toggles2 = order_split(session, thismeal.toggle2)
            departments = department_split(session)
            thisorder.notes = ''
            attend = session.query(Attendee).filter_by(public_id=cherrypy.session['staffer_id'])
            session.close()
            
            return template.render(order=thisorder,
                                   meal=thismeal,
                                   attendee=attend,
                                   toppings=toppings,
                                   toggles1=toggles1,
                                   toggles2=toggles2,
                                   departments=departments,
                                   message=message,
                                   c=c)
        elif not message:
            print('start no meal id')
            raise HTTPRedirect('staffer_order_list?message="You must specify a meal or order ID to create/edit an order."')
        
    @cherrypy.expose
    @restricted
    def staffer_meal_list(self, message='', display_all=False):
        """
        Display list of meals staffer is eligible for, unless requested to show all
        """
        template = env.get_template('staffer_meal_list.html')
        session = models.new_sesh()
        
        hours, shifts = ss_eligible(cherrypy.session['badge_num'], return_shifts=True)
        
        if hours < cfg.ss_hours:
            # todo: change this to be a list of messages so they can get their own lines and more easily have multiple
            message += 'You are not scheduled for enough volunteer hours to be eligible for Staff Suite.\n' \
                      'You will need to get a Department Head to authorize any orders you place.'
        
        meals = session.query(Meal).all()
        sorted_shifts = combine_shifts(shifts)
        meal_display = []
        
        for meal in meals:
            print("checking meal")
            eligible = carryout_eligible(sorted_shifts, meal.start_time, meal.end_time)
            
            
            if eligible:
                meal.eligible = True
                
            if eligible or display_all:
                meal_display.append(meal)
               
        if len(meal_display) == 0:
            message += 'You do not have any shifts that are eligible for Carryout.\n' \
                            'For eligibility rules see: link'  # todo: add link or change text
        
        session.close()
        
        return template.render(message=message,
                               meallist=meal_display,
                               c=c)
            
        

    @cherrypy.expose
   # @restricted
    #@admin_req todo: setup admin_req for requiring admin access
    def staffer_order_list(self, message='', order_id=''):
        # todo: check if eligible to staff suite at all, display warning message at top if not
        # letting user know orders will need to be overidden by a dept head.
        template = env.get_template('order_list.html')
        session = models.new_sesh()

        # this should be triggered if an edit button is clicked from the list
        if order_id:
            raise HTTPRedirect('order_edit?order_id='+order_id)

        # todo: list only orders associated with session['staffer_id']
        order_list = session.query(Order).options(joinedload('meal')).all()
        
        session.close()
        
        return template.render(message=message,
                               order_list=order_list,
                               c=c)

    @cherrypy.expose
    # @admin_req
    def config(self, message='', database_url=''):
        template = env.get_template('config.html')
        
        if database_url:
            print('-----------------------')
            print('saving config')
            # todo: save to config file
            
        print('---------------------')
        print('config loading')
        cherrypy_cfg = json.dumps(cfg.cherrypy, indent=4)
        print(cherrypy_cfg)
        print(type(cherrypy_cfg))
        return template.render(message=message,
                               cherrypy_cfg=cherrypy_cfg,
                               c=c,
                               cfg=cfg)
    
    
    @cherrypy.expose
    # @restricted
    def dept_test(self):
        template = env.get_template('dept_test.html')
        REQUEST_HEADERS = {'X-Auth-Token': cfg.apiauthkey}
        # data being sent to API
        request_data = {'method': 'attendee.search',
                        'params': ['kamikaze wombat', 'full']}
        request = requests.post(url=cfg.api_endpoint, json=request_data, headers=REQUEST_HEADERS)
        response = json.loads(request.text)
        result = response['result'][0]['shifts']
        print('--------------------')
        #print(result)
        #print(type(result))
        start = parse(result[0]['job']['start_time'])
        end = parse(result[0]['job']['end_time'])
        test = relativedelta(end, start)
        
        print(test)
        print(test.hours)
        print(type(test.hours))
        return template.render(text=response, type=type(result))
