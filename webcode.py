# sections of this are copied from https://github.com/magfest/ubersystem/blob/master/uber/site_sections/signups.py
# then modified for my needs.
import json
import requests

import cherrypy
from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal
import pytz
import sqlalchemy.orm.exc
from sqlalchemy.orm import joinedload, subqueryload

from config import env, cfg, c
from decorators import *
import models
from models.attendee import Attendee
from models.meal import Meal
from models.order import Order
from models.department import Department
from models.dept_order import DeptOrder
import shared_functions
from shared_functions import api_login, HTTPRedirect, order_split, order_selections, \
                         meal_join, meal_split, meal_blank_toppings, department_split, \
                        ss_eligible, carryout_eligible, combine_shifts, return_selected_only, \
                        con_tz, utc_tz, is_admin, is_ss_staffer, is_dh


class Root:
    
    @restricted
    @cherrypy.expose
    def index(self, load_depts=False):
        raise HTTPRedirect('staffer_meal_list')
        template = env.get_template('index.html')
        if load_depts:
            session = models.new_sesh()
            shared_functions.load_departments(session)
            session.close()
            
        return template.render(c=c)

    @cherrypy.expose
    def login(self, message=[], first_name='', last_name='',
              email='', zip_code='', original_location=None, logout=False):
        original_location = shared_functions.create_valid_user_supplied_redirect_url(original_location,
                                                                                     default_url='staffer_order_list')
        error = False
        messages = []
        if message:
            text = message
            messages.append(text)
            
        if logout:
            cherrypy.lib.sessions.expire()
            raise HTTPRedirect('login?message=Succesfully logged out')
            
        if first_name and last_name and email and zip_code:
            response = api_login(first_name=first_name, last_name=last_name,
                                 email=email, zip_code=zip_code)
            
            if 'error' in response:
                messages.append(response['error']['message'])
                error = True
                
            if not error:
                # is staff?
                if not response['result']['staffing']:
                    messages.append('You are not currently signed up as staff/volunteer.'
                              'See below for information on how to volunteer.')
                    not_volunteer = True
            
            if not error:
                # ensure_csrf_token_exists()
                cherrypy.session['staffer_id'] = response['result']['public_id']
                cherrypy.session['badge_num'] = response['result']['badge_num']
                session = models.new_sesh()
                print('succesful login, updating record')
                # add or update attendee record in DB
                try:
                    attendee = session.query(Attendee).filter_by(public_id=response['result']['public_id']).one()
                    
                    # only update record if different
                    if not attendee.full_name == response['result']['full_name'] \
                            or not attendee.badge_num == response['result']['badge_num']:
                        attendee.full_name = response['result']['full_name']
                        attendee.badge_num = response['result']['badge_num']
                        session.commit()
                    print('record update complete')
                except sqlalchemy.orm.exc.NoResultFound:
                    print('new attendee login, creating record')
                    attendee = Attendee()
                    attendee.badge_num = response['result']['badge_num']
                    attendee.public_id = response['result']['public_id']
                    attendee.full_name = response['result']['full_name']
                    session.add(attendee)
                    session.commit()
                    
                session.close()

                if not cfg.orders_open and not is_admin:
                    messages.append('Orders are not yet open')
                else:
                    raise HTTPRedirect(original_location)

        template = env.get_template('login.html')
        return template.render(messages=messages,
                               first_name=first_name,
                               last_name=last_name,
                               email=email,
                               zip_code=zip_code,
                               original_location=original_location,
                               c=c)

    @cherrypy.expose
    # @restricted
    @admin_req
    def meal_setup_list(self, message=[], id=''):
    
        messages = []
        if message:
            text = message
            messages.append(text)
            
        session = models.new_sesh()
        
        # this should be triggered if an edit button is clicked from the list
        if id:
            raise HTTPRedirect('meal_edit?meal_id='+id)

        meallist = session.query(Meal).order_by(models.meal.Meal.start_time).all()
        session.close()
        
        for meal in meallist:
            meal.start_time = con_tz(meal.start_time)

        template = env.get_template('meal_setup_list.html')
        return template.render(messages=messages,
                               meallist=meallist,
                               c=c)

    @cherrypy.expose
    @admin_req
    # @restricted
    def meal_edit(self, meal_id='', message=[], **params):
    
        messages = []
        if message:
            text = message
            messages.append(text)
            
        # save new / updated meal
        if 'meal_name' in params:
            session = models.new_sesh()
            try:
                # tries to load id from params, if not there or blank does new meal
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
            thismeal.start_time = utc_tz(params['start_time'])
            thismeal.end_time = utc_tz(params['end_time'])
            thismeal.cutoff = utc_tz(params['cutoff'])
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
                thismeal.start_time = con_tz(thismeal.start_time)
                thismeal.end_time = con_tz(thismeal.end_time)
                thismeal.cutoff = con_tz(thismeal.cutoff)
                # loads list of existing toppings, adds blank toppings to list up to configured quantity
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

        template = env.get_template("meal_edit.html")
        return template.render(meal=thismeal,
                               toppings=toppings,
                               toggles1=toggles1,
                               toggles2=toggles2,
                               messages=messages,
                               c=c)


    @restricted
    @cherrypy.expose
    def order_edit(self, meal_id='', save_order='', order_id='', message=[], notes='', delete_order=False,
                   dh_edit=False, **params):
        # todo: do something with Uber allergies info
        # todo: link to allergies SOP somewhere
        
        # todo: needs to check if the dept_order for selected meal time and department is marked started,
        # todo: if dept_order is started do not allow saving new order
        
        # todo: html needs to do extra stuff if is DH
        # todo: department select dropdown needs to restrict based upon if a department's order is already being processed or has been.
        messages = []
        if message:
            text = message
            messages.append(text)
            
        session = models.new_sesh()
        thisorder = ''
        thismeal = ''
        
        # parameter save_order should only be present if submit clicked
        if save_order:
            print('start save_order')
            # : save it lol
            
            try:
                thisorder = session.query(Order).filter_by(id=order_id).one()
                #does not update if not belong to user or user is DH/Admin
                if not thisorder.attendee.public_id == cherrypy.session['staffer_id']:
                    if not shared_functions.is_dh(cherrypy.session['staffer_id']):
                        if not shared_functions.is_admin(cherrypy.session['staffer_id']):
                            raise HTTPRedirect("staffer_meal_list?message=This isn't your order.")
                        
                if thisorder.locked and not cherrypy.session['is_admin']:
                    raise HTTPRedirect("staffer_meal_list?message=This order has already been started by Staff Suite"
                                       " and cannot be changed except by Staff Suite Admins")
            except sqlalchemy.orm.exc.NoResultFound:
                thisorder = Order()
                
            if dh_edit:
                # actually verifies you are admin and not just you edited URL
                print('starting dh_edit')
                if is_dh(cherrypy.session['staffer_id']) or is_admin(cherrypy.session['staffer_id']):
                    print('is actualy dh or admin')
                    try:
                        attend = session.query(Attendee).filter_by(badge_num=params['badge_number']).one()
                    except sqlalchemy.orm.exc.NoResultFound:
                        response = shared_functions.lookup_attendee(params['badge_number'])
                        attend = Attendee()
                        attend.badge_num = response['result']['badge_num']
                        attend.public_id = response['result']['public_id']
                        attend.full_name = response['result']['full_name']
                        session.add(attend)
                        session.commit()
                        
                    thisorder.attendee_id = attend.public_id
                    
                else:
                    raise HTTPRedirect('staffer_meal_list?message=You must be DH or admin to use this feature')
            else:
                print('not dh_edit')
                thisorder.attendee_id = cherrypy.session['staffer_id']
             
            thisorder.department_id = params['department']
            thisorder.meal_id = save_order  # save order kinda wonky, data will be meal id if 'Submit' is clicked
            # todo: do something with overridden field
            thisorder.toggle1 = order_selections(field='toggle1', params=params, is_toggle=True)
            thisorder.toggle2 = order_selections(field='toggle2', params=params, is_toggle=True)
            thisorder.toppings = order_selections(field='toppings', params=params)
            thisorder.notes = notes
            
            session.add(thisorder)
            session.commit()
            session.close()
            
            raise HTTPRedirect('staffer_order_list?message=Succesfully saved order')
        
        if order_id:
            print('start order_id')
            # load order
            thisorder = session.query(Order).filter_by(id=order_id).one()
            thismeal = thisorder.meal  # session.query(Meal).filter_by(id=thisorder.meal_id).one()
            if dh_edit:
                try:
                    attend = session.query(Attendee).filter_by(badge_num=params['badge_number']).one()
                except sqlalchemy.orm.exc.NoResultFound:
                    response = shared_functions.lookup_attendee(params['badge_number'])
                    attend = Attendee()
                    attend.badge_num = response['result']['badge_num']
                    attend.public_id = response['result']['public_id']
                    attend.full_name = response['result']['full_name']
                    session.add(attend)
                    session.commit()
            else:
                attend = session.query(Attendee).filter_by(public_id=cherrypy.session['staffer_id']).one()
                
            session.close()
            if not attend.public_id == cherrypy.session['staffer_id']:
                if not shared_functions.is_dh(cherrypy.session['staffer_id']):
                    if not shared_functions.is_admin(cherrypy.session['staffer_id']):
                        raise HTTPRedirect("staffer_meal_list?message=This isn't your order.")
                    
            thismeal.start_time = con_tz(thismeal.start_time)
            thismeal.end_time = con_tz(thismeal.end_time)
            thismeal.cutoff = con_tz(thismeal.cutoff)
            toppings = order_split(session, choices=thismeal.toppings, orders=thisorder.toppings)
            toggles1 = order_split(session, choices=thismeal.toggle1, orders=thisorder.toggle1)
            toggles2 = order_split(session, choices=thismeal.toggle2, orders=thisorder.toggle2)
            departments = department_split(session, thisorder.department_id)
            messages.append('Order ID ' + str(order_id) + ' loaded')
            
            template = env.get_template('order_edit.html')
            return template.render(order=thisorder,
                                   meal=thismeal,
                                   attendee=attend,
                                   toppings=toppings,
                                   toggles1=toggles1,
                                   toggles2=toggles2,
                                   departments=departments,
                                   messages=messages,
                                   dh_edit=dh_edit,
                                   c=c)
            
        if meal_id:
            print('start meal_id')
            # attempt new order from meal_id
            if dh_edit and (is_dh(cherrypy.session['staffer_id']) or is_admin(cherrypy.session['staffer_id'])):
                try:
                    attend = session.query(Attendee).filter_by(badge_num=params['badge_number']).one()
                except sqlalchemy.orm.exc.NoResultFound:
                    response = shared_functions.lookup_attendee(params['badge_number'])
                    attend = Attendee()
                    attend.badge_num = response['result']['badge_num']
                    attend.public_id = response['result']['public_id']
                    attend.full_name = response['result']['full_name']
                    session.add(attend)
                    session.commit()
                try:
                    thisorder = session.query(Order).filter_by(attendee_id=attend.public_id, meal_id=meal_id).one()

                    raise HTTPRedirect('order_edit?dh_edit=True&badge_number=' + str(params['badge_number']) +
                                       '&order_id=' + str(thisorder.id) +
                                       '&message=An order already exists for this Meal, previously created '
                                       'order selections loaded.')
                except sqlalchemy.orm.exc.NoResultFound:
                    pass
            else:
                try:
                    thisorder = session.query(Order).filter_by(attendee_id=cherrypy.session['staffer_id'],
                                                               meal_id=meal_id).one()
                    raise HTTPRedirect('order_edit?order_id=' + str(thisorder.id) +
                                       '&message=An order already exists for this Meal, previously created order selections '
                                       'loaded.')
                except sqlalchemy.orm.exc.NoResultFound:
                    pass
            if dh_edit:
                try:
                    attend = session.query(Attendee).filter_by(badge_num=params['badge_number']).one()
                except sqlalchemy.orm.exc.NoResultFound:
                    response = shared_functions.lookup_attendee(params['badge_number'])
                    attend = Attendee()
                    attend.badge_num = response['result']['badge_num']
                    attend.public_id = response['result']['public_id']
                    attend.full_name = response['result']['full_name']
                    session.add(attend)
                    session.commit()
                    
            else:
                attend = session.query(Attendee).filter_by(public_id=cherrypy.session['staffer_id']).one()

            thismeal = session.query(Meal).filter_by(id=meal_id).one()
            session.close()
            
            thismeal.start_time = con_tz(thismeal.start_time)
            thismeal.end_time = con_tz(thismeal.end_time)
            thismeal.cutoff = con_tz(thismeal.cutoff)
            thisorder = Order()
            thisorder.attendee_id = cherrypy.session['staffer_id']
            toppings = order_split(session, thismeal.toppings)
            toggles1 = order_split(session, thismeal.toggle1)
            toggles2 = order_split(session, thismeal.toggle2)
            departments = department_split(session)
            thisorder.notes = ''
            
            template = env.get_template('order_edit.html')
            return template.render(order=thisorder,
                                   meal=thismeal,
                                   attendee=attend,
                                   toppings=toppings,
                                   toggles1=toggles1,
                                   toggles2=toggles2,
                                   departments=departments,
                                   messages=message,
                                   dh_edit=dh_edit,
                                   c=c)
        # todo: add delete/cancel order function
        if delete_order:
            raise HTTPRedirect('order_delete_comfirm?order_id=' + str(delete_order))
        
        # if nothing else matched, not creating, loading, saving, or deleting.  therefore, error.
        raise HTTPRedirect('staffer_order_list?message=You must specify a meal or order ID to create/edit an order.')
    
    @cherrypy.expose
    @restricted
    def order_delete_confirm(self, order_id='', confirm=False):
        session = models.new_sesh()
        
        thisorder = session.query(Order).filter_by(id=order_id).one()
        
        if confirm:
            if thisorder.attendee_id == cherrypy.session['staffer_id']:
                session.delete(thisorder)
                session.commit()
                session.close()
                raise HTTPRedirect('staffer_order_list?message=Order Deleted.')
            else:
                session.close()
                raise HTTPRedirect('staffer_order_list?message=Order does not belong to you?')
        
        template = env.get_template('order_delete_confirm.html')
        return template.render(
            order=thisorder,
            c=c
        )

    @cherrypy.expose
    # @restricted
    @admin_req
    def meal_delete_confirm(self, meal_id='', confirm=False):
        session = models.new_sesh()
        # todo: something to block malicious users from doctoring links and tricking admins into deleting meals.
        #       perhaps check if meal_delete_confirm is in link at login page?
        
        # todo: add meal name, time to html
        thismeal = session.query(Meal).filter_by(id=meal_id).one()
    
        if confirm:
            
            session.delete(thismeal)
            session.commit()
            session.close()
            raise HTTPRedirect('meal_setup_list?message=Meal Deleted.')
            
        template = env.get_template('meal_delete_confirm.html')
        return template.render(
            meal=thismeal,
            c=c
        )
        
        
    @cherrypy.expose
    @restricted
    def staffer_meal_list(self, message=[], id='', display_all=False):
        """
        Display list of meals staffer is eligible for, unless requested to show all
        """
        # todo: display some information about order status for available meals
        # present if Create Order button clicked
        if id:
            raise HTTPRedirect('order_edit?meal_id='+id)
        
        messages = []
        if message:
            text = message
            messages.append(text)
            
        session = models.new_sesh()
        
        eligible = ss_eligible(cherrypy.session['badge_num'])
        
        if not eligible:
            print("appending not enough hours")
            messages.append('You are not scheduled for enough volunteer hours to be eligible for Staff Suite.\n'
                            'You will need to get a Department Head to authorize any orders you place.')
        
        meals = session.query(Meal).all()
        sorted_shifts = combine_shifts(cherrypy.session['badge_num'])
        meal_display = []
        
        session.close()  # session close is here to make sure the eligible mark doesn't get put into the DB
                         # yes I know it should not because not a column, but for my own paranoia
        now = datetime.now()
        now = now.replace(tzinfo=tzlocal())
        now = now.astimezone(pytz.utc)
        now = now.replace(tzinfo=None)
        for meal in meals:
            # print("checking meal")
            meal.eligible = carryout_eligible(sorted_shifts, meal.start_time, meal.end_time)
            
            if meal.eligible or display_all:
                delta = relativedelta(meal.end_time, now)
                # rd is negative if first item is before second
                rd = 0
                # todo: section removed for testing since West is currently in the past.
                """"
                rd += delta.minutes
                rd += delta.hours * 60
                rd += delta.days * 1440
                """
                if rd >= 0 or display_all:
                    meal_display.append(meal)
        
        if len(meal_display) == 0:
            messages.append('You do not have any shifts that are eligible for Carryout.'
                            'For eligibility rules see: add link')  # todo: add link or change text
        
        for thismeal in meal_display:
            thismeal.start_time = con_tz(thismeal.start_time)
            thismeal.end_time = con_tz(thismeal.end_time)
            thismeal.cutoff = con_tz(thismeal.cutoff)
        
        template = env.get_template('staffer_meal_list.html')
        return template.render(messages=messages,
                               meallist=meal_display,
                               c=c)
            
        

    @cherrypy.expose
    @restricted
    def staffer_order_list(self, message=[], order_id=''):
        # todo: check if eligible to staff suite at all, display warning message at top if not
        # letting user know orders will need to be overidden by a dept head.
        
        messages = []
        if message:
            text = message
            messages.append(text)
            
        session = models.new_sesh()

        # this should be triggered if a create button is clicked from the list
        if order_id:
            raise HTTPRedirect('order_edit?order_id='+order_id)

        # todo: list only orders associated with session['staffer_id']
        order_query = session.query(Order).options(joinedload('meal')).all()
        
        session.close()
        order_list = list()
        for order in order_query:
            try:
                order.meal.start_time = con_tz(order.meal.start_time)
                order.meal.end_time = con_tz(order.meal.end_time)
                order.meal.cutoff = con_tz(order.meal.cutoff)
                order_list.append(order)
            except AttributeError:
                print('order# ' + str(order.id) + ' is orphaned and has no valid meal associated')

        template = env.get_template('order_list.html')
        return template.render(messages=messages,
                               order_list=order_list,
                               c=c)

    @cherrypy.expose
    # @restricted
    @admin_req
    def config(self, message=[], database_url=''):
        messages = []

        if message:
            text = message
            messages.append(text)
            
        if database_url:
            print('-----------------------')
            print('saving config')
            # todo: save to config file
            
        print('---------------------')
        print('config loading')
        cherrypy_cfg = json.dumps(cfg.cherrypy, indent=4)
        print(cherrypy_cfg)
        print(type(cherrypy_cfg))
        
        template = env.get_template('config.html')
        return template.render(messages=messages,
                               cherrypy_cfg=cherrypy_cfg,
                               c=c,
                               cfg=cfg)

    @cherrypy.expose
    @dh_or_admin
    def dept_order_selection(self, **params):
        """
        Allows DH to select meal time and which department they wish to view the dept_order for.
        Filters meal list to only show future meals by default (by end time, not start time)
        Filters selectable departments to only include ones the DH is assigned to unless user is Admin
        """
        # meal_id would be present if Select button is clicked, sends to selected dept_order
        if 'meal_id' in params:
            raise HTTPRedirect('dept_order?meal_id=' + str(params['meal_id']) + '&dept_id=' + str(params['dept_id']))
        
        session = models.new_sesh()
        departments = department_split(session)
        
        # todo: filter by future meals, by end time of meal
        meal_list = session.query(Meal).all()
        
        session.close()
        template = env.get_template("dept_order_selection.html")
        return template.render(depts=departments,
                               meals=meal_list,
                               c=c)
        

    @cherrypy.expose
    @dh_or_admin
    def dept_order(self, meal_id, dept_id, message="", **params):
        """
        Usable by Department Heads and admins
        list of Staffer orders for selected meal and department
        Can override ones not already eligible
        Can edit existing ones if need be (usually shouldn't)
        Can create new orders for specified badge number
        Will disable all these features once the dept order is started
        """
        # todo: needs to check if the dept_order for selected meal time and department is marked started
        # todo: if started needs to put notice at top that it is started.  if completed, same.
        
        messages = []
        if message:
            text = message
            messages.append(text)
        
        session = models.new_sesh()
        
        dept = session.query(Department).filter_by(id=dept_id).one()
        dept_name = dept.name
        
        order_list = session.query(Order).filter_by(meal_id=meal_id, department_id=dept_id).options(subqueryload(Order.attendee)).all()
        # todo: check each order to see if the attendee is eligible for this meal, highlight in html if not
        thismeal = session.query(Meal).filter_by(id=meal_id).one()
        
        for order in order_list:
            # print("checking meal")
            sorted_shifts = combine_shifts(order.attendee.badge_num)
            order.eligible = carryout_eligible(sorted_shifts, thismeal.start_time, thismeal.end_time)

        thismeal.start_time = con_tz(thismeal.start_time)
        thismeal.end_time = con_tz(thismeal.end_time)
        thismeal.cutoff = con_tz(thismeal.cutoff)
           
        if len(order_list) == 0:
            messages.append('Your department does not have any orders for this meal.')

        # tries to load existing dept order, if none creates a new one.
        try:
            this_dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            this_dept_order = DeptOrder()
            this_dept_order.dept_id = dept_id
            this_dept_order.meal_id = meal_id
            session.add(this_dept_order)
            session.commit()
        
        if 'contact_info' in params:
            # save changes to dept_order
            this_dept_order.contact_info = params['contact_info']
            session.commit()
            messages.append('Department order contact info successfully updated.')
        
        # reload order since commit flushes it from cache (apparently)
        this_dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()
        thismeal = session.query(Meal).filter_by(id=meal_id).one()
        session.close()
        
        if this_dept_order.started:
            this_dept_order.start_time = con_tz(this_dept_order.start_time)
        if this_dept_order.completed:
            this_dept_order.completed_time = con_tz(this_dept_order.completed_time)
            
        template = env.get_template('dept_order.html')
        return template.render(dept=dept_name,
                               orders=order_list,
                               dept_order=this_dept_order,
                               meal=thismeal,
                               messages=messages,
                               c=c)
        
    @cherrypy.expose
    @dh_or_admin
    def order_override(self, order_id, meal_id, dept_id, remove_override=False):
        """
        Override or remove override on an order
        :param order_id:
        :param remove_override:
        :return:
        """
        session = models.new_sesh()
        dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()
        if dept_order.started:
            raise HTTPRedirect('dept_order_selection?message=The order for your department for this meal has already been started.')
        order = session.query(Order).filter_by(id=order_id).options(subqueryload(Order.attendee)).one()
        if remove_override:
            order.overridden = False
        else:
            order.overriden = True
        session.commit()
        session.close()
        raise HTTPRedirect('dept_order?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                           '&message=Override added for ' + str(order.attendee.badge_num))
           
    
    @cherrypy.expose
    @ss_staffer
    def ssf_meal_list(self, display_all=False):
        """
        Displays list of Meals to be fulfilled
        """
        session = models.new_sesh()
        
        meals = session.query(Meal).all()
        shift_buffer = relativedelta(minutes=cfg.schedule_tolerance)
        meal_list = []
        now = datetime.now()
        now = now.replace(tzinfo=tzlocal())
        now = now.astimezone(pytz.utc)
        now = now.replace(tzinfo=None)
        for meal in meals:
            # rd is positive if first item is after second.
            rd = relativedelta(meal.end_time + shift_buffer, now)
            # skips adding to list if item is in past
            """ removed during testing cause West is in past
            if rd.days < 0 and not display_all:
                continue
            if rd.hours < 0 and not display_all:
                continue
            if rd.minutes < 0 and not display_all:
                continue
            """
            # only runs these two lines if meal is in future or display_all is True
            count = session.query(Order).filter_by(meal_id=meal.id).count()
            session.close()
            # todo: figure out how to count just ones that are still in future
            meal_list.append({'id': meal.id, 'name': meal.meal_name, 'start': con_tz(meal.start_time),
                              'end': con_tz(meal.end_time), 'count': count})
        
        template = env.get_template('ssf_meal_list.html')
        return template.render(meallist=meal_list,
                               c=c)

    @cherrypy.expose
    @ss_staffer
    def ssf_dept_list(self, meal_id):
        """
        For chosen meal, shows list of departments with how many orders are currently submitted for that department
        Fulfilment staff can select a department to view order details.
        """
        session = models.new_sesh()
        
        depts = session.query(models.department.Department).all()
        dept_list = list()
        total_orders = 0
        
        for dept in depts:
            count = session.query(Order).filter_by(department_id=dept.id, meal_id=meal_id).count()
            dept_list.append((dept.name, count, dept.id))
            total_orders += count
        
        # print(dept_list)
        session.close()
        template = env.get_template('ssf_dept_list.html')
        return template.render(depts=dept_list,
                               meal_id=meal_id,
                               total=total_orders,
                               c=c)
        
        
    @cherrypy.expose
    # @restricted
    @ss_staffer
    def ssf_orders(self, meal_id, dept_id, message=[]):
        """
        Shows list of orders for selected meal and dept.
        Has buttons to lock order for fulfilment, or if already locked by mistake to unlock.
        Once order is locked buttons to print all orders or individual orders become available
        Button to mark department order complete - notifies departments it's ready for pickup
        """
        class Horder:
            # order for display in HTML
            id = ''
            toggle1 = ''
            toggle2 = ''
            toppings = []
            notes = ''
            
            badge_num = ''
            full_name = ''
            
            #meal_id = ''

        messages = []
        if message:
            text = message
            messages.append(text)

        session = models.new_sesh()
        
        order_list = session.query(Order).filter_by(department_id=dept_id, meal_id=meal_id)\
            .options(joinedload(Order.attendee)).all()
        thismeal = session.query(Meal).filter_by(id=meal_id).one()
        
        dept = session.query(Department).filter_by(id=dept_id).one()
        dept_name = dept.name
        
        orders = list()
        for order in order_list:
            horder = Horder()
            horder.id = order.id
            horder.toggle1 = return_selected_only(session, choices=thismeal.toggle1, orders=order.toggle1)
            #print('----------toggle1----------------')
            #print(horder.toggle1)
            horder.toggle2 = return_selected_only(session, choices=thismeal.toggle2, orders=order.toggle2)
            horder.toppings = return_selected_only(session, choices=thismeal.toppings, orders=order.toppings)
            horder.notes = order.notes
            horder.badge_num = order.attendee.badge_num
            horder.full_name = order.attendee.full_name
            orders.append(horder)
            
        session.close()
        template = env.get_template('ssf_orders.html')
        return template.render(dept=dept_name,
                               dept_id=dept_id,
                               order_list=orders,
                               meal=thismeal,
                               messages=messages,
                               c=c)


    def order_detail(self):
        """
        Displays details of an order in a popup for fulfilment purposes
        """
        
    def print_order(self):
        """
        Prints order from popup screen then closes itself
        """
        
