# sections of this are copied from https://github.com/magfest/ubersystem/blob/master/uber/site_sections/signups.py
# then modified for my needs.
import json
import requests

import cherrypy
from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal
import pdfkit
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
from models.checkin import Checkin
import shared_functions
from shared_functions import api_login, HTTPRedirect, order_split, order_selections, allergy_info, \
                     meal_join, meal_split, meal_blank_toppings, department_split, create_dept_order, \
                     ss_eligible, carryout_eligible, combine_shifts, return_selected_only, \
                     con_tz, utc_tz, now_utc, now_contz, is_admin, is_ss_staffer, is_dh, return_not_selected
import slack_bot


class Root:
    
    @restricted
    @cherrypy.expose
    def index(self):
        raise HTTPRedirect('staffer_meal_list')
        
    @cherrypy.expose
    def login(self, message=[], first_name='', last_name='',
              email='', zip_code='', original_location=None, logout=False):
        """
        Login Screen.  Can redirect to original destination.
        :param message:
        :param first_name:
        :param last_name:
        :param email:
        :param zip_code:
        :param original_location:
        :param logout:
        :return:
        """
        original_location = shared_functions.create_valid_user_supplied_redirect_url(original_location,
                                                                                     default_url='staffer_meal_list')
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
                print(response['error']['message'])
            """ decided it didn't make sense to keep out people not marked staff/volunteer in Uber
            because then people who decide to volunteer after arriving won't be able to login.
            Hours requirements will still require DH override for people who don't have enough hours marked down
            if not error:
                # is staff?
                if not response['result']['staffing']:
                    messages.append('You are not currently signed up as staff/volunteer.'
                              'See below for information on how to volunteer.')
                    not_volunteer = True
            """
            
            if not error:
                # ensure_csrf_token_exists()
                cherrypy.session['staffer_id'] = response['result']['public_id']
                cherrypy.session['badge_num'] = response['result']['badge_num']
                
                if is_ss_staffer(cherrypy.session['staffer_id']):
                    cherrypy.session['is_ss_staffer'] = True
                else:
                    cherrypy.session['is_ss_staffer'] = False
                    
                if is_admin(cherrypy.session['staffer_id']):
                    cherrypy.session['is_admin'] = True
                else:
                    cherrypy.session['is_admin'] = False
                    
                if is_dh(cherrypy.session['staffer_id']):
                    cherrypy.session['is_dh'] = True
                else:
                    cherrypy.session['is_dh'] = False
                    
                    # food manager tag is for a person who only has this specific privilige, not DH or admin also.
                if cherrypy.session['staffer_id'] in cfg.food_managers and not cherrypy.session['is_dh'] \
                        and not cherrypy.session['is_admin']:
                    cherrypy.session['is_food_manager'] = True
                    cherrypy.session['is_dh'] = True
                else:
                    cherrypy.session['is_food_manager'] = False
                    
                # check if orders open
                if not cfg.orders_open():
                    if not cherrypy.session['is_ss_staffer']:
                        if not cherrypy.session['is_admin']:
                            if not cherrypy.session['is_dh']:
                                # cherrypy.lib.sessions.expire()  # probably not needed
                                raise HTTPRedirect('login?message=Orders are not yet open.  You can login beginning at '
                                                   + con_tz(c.EPOCH).strftime(cfg.date_format) + ' ID: ' +
                                                   str(cherrypy.session['staffer_id']))

                session = models.new_sesh()
                # print('succesful login, updating record')
                # add or update attendee record in DB
                try:
                    attendee = session.query(Attendee).filter_by(public_id=response['result']['public_id']).one()
                    
                    # only update record if different
                    if not attendee.full_name == response['result']['full_name'] \
                            or not attendee.badge_num == response['result']['badge_num']:
                        attendee.full_name = response['result']['full_name']
                        attendee.badge_num = response['result']['badge_num']
                        session.commit()
                    # print('record update complete')
                except sqlalchemy.orm.exc.NoResultFound:
                    # print('new attendee login, creating record')
                    attendee = Attendee()
                    attendee.badge_num = response['result']['badge_num']
                    attendee.public_id = response['result']['public_id']
                    attendee.full_name = response['result']['full_name']
                    session.add(attendee)
                    session.commit()
                    
                session.close()

                raise HTTPRedirect(original_location)

        template = env.get_template('login.html')
        return template.render(messages=messages,
                               first_name=first_name,
                               last_name=last_name,
                               email=email,
                               zip_code=zip_code,
                               original_location=original_location,
                               c=c,
                               isdev=cfg.devenv)

    @cherrypy.expose
    @admin_req
    def meal_setup_list(self, message=[], id=''):
    
        messages = []
        if message:
            text = message
            messages.append(text)
            
        session = models.new_sesh()
        
        # this should be triggered if an edit button is clicked from the list
        if id:
            session.close()
            raise HTTPRedirect('meal_edit?meal_id='+id)

        meallist = session.query(Meal).order_by(models.meal.Meal.start_time).all()
        session.close()
        
        for meal in meallist:
            meal.start_time = con_tz(meal.start_time)

        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }
        
        template = env.get_template('meal_setup_list.html')
        return template.render(messages=messages,
                               meallist=meallist,
                               session=session_info,
                               c=c)

    @cherrypy.expose
    @ss_staffer
    def dinein_checkin(self):
        session = models.new_sesh()
        now = now_utc()
        current_meals = session.query(Meal).filter(Meal.start_time < now, Meal.end_time > now).order_by(Meal.end_time).all()
        if not current_meals:
            current_meal = None
        else:
            current_meal = current_meals[-1]
        session.close()

        template = env.get_template("dinin_checkin.html")

        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }

        return template.render(current_meal=current_meal, c=c, session=session_info)

    @cherrypy.expose
    @ss_staffer
    def checkin_badge(self, meal_id='', badge=''):
        if badge[0] == "~":
            badge = shared_functions.barcode_to_badge(badge)
        else:
            try:
                badge = int(badge)
            except ValueError:
                return json.dumps({"success": False, "badge": badge, "reason": "Not a number?"})
            
        if not badge:
            return json.dumps({"success": False, "badge": badge, "reason": "Could not locate badge."})
        
        #if not meal_id:
         #   return json.dumps({"success": False, "badge": badge, "reason": ""})
        
        session = models.new_sesh()
        meal = session.query(Meal).filter(Meal.id == meal_id).one_or_none()
        #if not meal:
        #    session.close()
        #    return json.dumps({"success": False, "badge": badge, "reason": "Could not find meal {}.".format(meal_id)})
        
        try:
            attend = session.query(Attendee).filter_by(badge_num=badge).one()
        except sqlalchemy.orm.exc.NoResultFound:
            response = shared_functions.lookup_attendee(badge)
            if 'error' in response:
                session.close()
                return json.dumps({"success": False, "badge": badge, "reason": "Badge # {} is not found in Reggie".format(badge)})
            attend = Attendee()
            attend.badge_num = response['result']['badge_num']
            attend.public_id = response['result']['public_id']
            attend.full_name = response['result']['full_name']
            session.add(attend)
            session.commit()
            
        if meal:
            order = session.query(Order).filter(Order.attendee_id == attend.public_id,
                                                Order.meal_id == meal.id).one_or_none()
            if order:
                sorted_shifts, response = combine_shifts(attend.badge_num, full=True, no_combine=True)
                user_exempt = False
                for dept in response['result']['assigned_depts_labels']:
                    if dept in cfg.exempt_depts:
                        user_exempt = True

                if cherrypy.session['is_dh'] or user_exempt:
                    eligible = True
                else:
                    eligible = carryout_eligible(sorted_shifts, meal.start_time, meal.end_time)
                
                # if their order is eligible for carryout, they get kicked out
                if eligible or user_exempt:
                    session.close()
                    return json.dumps({"success": False, "badge": badge, "reason": "Attendee {} has placed a delivery order for this meal.".format(badge)})
        
        allergy_msg = ""
        allergies = allergy_info(badge)
        for allergy in allergies['standard_labels']:
            allergy_msg += allergy+"<br>"
        allergy_msg += allergies['freeform']
        if meal:
            checkin = session.query(Checkin).filter(Checkin.attendee_id == attend.public_id, Checkin.meal_id == meal.id).all()
        else:
            checkin = session.query(Checkin).filter(Checkin.attendee_id == attend.public_id,
                                                    Checkin.meal_id == None).all()
        if checkin and meal:
            session.close()
            return json.dumps({"success": False, "badge": badge, "reason": "Badge is already checked in for this meal.", "allergies": allergy_msg})
        
        if not shared_functions.ss_eligible(badge):
            session.close()
            return json.dumps({"success": False, "badge": badge, "reason": "Badge is not eligible for food. Please see STOPS."})
        
        if meal:
            checkin = Checkin(attendee_id=attend.public_id, meal_id=meal.id)
        else:
            if checkin:
                # if not meal, but checkin.  ie if attempting checkin not during meal AND this has one or more checkins.
                for item in checkin:
                    delta = relativedelta(item.timestamp, datetime.utcnow())
                    # if a previously received checkin NOT associated with a meal is with 2 hours of current non meal checkin
                    if not item.meal_id and abs(delta.hours) <= 1 and abs(delta.days) == 0:
                        session.close()
                        return json.dumps({"success": True, "badge": badge, "reason": "", "allergies": allergy_msg})
            checkin = Checkin(attendee_id=attend.public_id, meal_id=None)
        session.add(checkin)
        session.commit()
        session.close()
        return json.dumps({"success": True, "badge": badge, "reason": "", "allergies": allergy_msg})

    @cherrypy.expose
    @admin_req
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
            thismeal.toggle3_title = params['toggle3_title']
            thismeal.toggle3 = meal_join(session, params, field='toggle3')
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
                toggles3 = meal_blank_toppings(meal_split(session, thismeal.toggle3), cfg.radio_select_count)
            except sqlalchemy.orm.exc.NoResultFound:
                message = 'Requested Meal ID '+meal_id+' not found'
                session.close()
                raise HTTPRedirect('meal_setup_list?message='+message)
            
            session.close()
            
        else:
            thismeal = Meal()
            thismeal.meal_name = ''
            thismeal.description = ''
            thismeal.toppings_title = ''
            thismeal.toggle1_title = ''
            thismeal.toggle2_title = ''
            thismeal.toggle3_title = ''
            # make blank boxes for new meal.
            toppings = meal_blank_toppings([], cfg.multi_select_count)
            toggles1 = meal_blank_toppings([], cfg.radio_select_count)
            toggles2 = meal_blank_toppings([], cfg.radio_select_count)
            toggles3 = meal_blank_toppings([], cfg.radio_select_count)

        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }
        
        template = env.get_template("meal_edit.html")
        return template.render(meal=thismeal,
                               toppings=toppings,
                               toggles1=toggles1,
                               toggles2=toggles2,
                               toggles3=toggles3,
                               messages=messages,
                               session=session_info,
                               c=c)


    @restricted
    @cherrypy.expose
    def order_edit(self, meal_id='', save_order='', order_id='', message=[], notes='', delete_order=False,
                   dh_edit=False, **params):
        
        # todo: department select dropdown needs to restrict based upon if a department's order is already being processed or has been.
        messages = []
        if message:
            text = message
            messages.append(text)

        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }
        
        thisorder = ''
        thismeal = ''
        
        if delete_order:
            raise HTTPRedirect('order_delete_comfirm?order_id=' + str(delete_order))

        session = models.new_sesh()
        
        # parameter save_order should only be present if submit clicked
        if save_order:
            # : save it lol
            
            # try to load existing order
            try:
                if dh_edit:
                    attend = session.query(Attendee).filter_by(badge_num=params['badge_number']).one()
                    thisorder = session.query(Order).filter_by(meal_id=save_order,
                                                               attendee_id=attend.public_id).one()
                else:
                    thisorder = session.query(Order).filter_by(meal_id=save_order,
                                                               attendee_id=cherrypy.session['staffer_id']).one()
                # does not update if not belong to user or user is DH/Admin
                if not thisorder.attendee.public_id == cherrypy.session['staffer_id']:
                    if not shared_functions.is_dh(cherrypy.session['staffer_id']):
                        if not shared_functions.is_admin(cherrypy.session['staffer_id']):
                            session.close()
                            raise HTTPRedirect("staffer_meal_list?message=This isn't your order.")
                
            except sqlalchemy.orm.exc.NoResultFound:
                # if no existing order create new order
                thisorder = Order()
                thismeal = session.query(Meal).filter_by(id=save_order).one()
                thisorder.meal = thismeal

            try:
                dept_order = session.query(DeptOrder).filter_by(meal_id=save_order,
                                                                dept_id=params['department']).one()
                dept_order_started = dept_order.started

            except sqlalchemy.orm.exc.NoResultFound:
                # it's fine if none there, can't be started if it's not created
                dept_order_started = False
                
            if dept_order_started or thisorder.locked:
                session.close()
                raise HTTPRedirect("staffer_meal_list?message=Your department's bundle "
                                   "has already been started by Staff Suite")

            hour = relativedelta(hours=1)
            now = datetime.utcnow() + hour
            rd = relativedelta(now, thisorder.meal.end_time)
            
            if rd.minutes > 0 or rd.hours > 0 or rd.days > 0:
                raise HTTPRedirect("staffer_meal_list?message=Pickup orders for this meal time are closed")
            
            if dh_edit:
                # actually verifies you are admin and not just you edited URL
                # print('starting dh_edit')
                if is_dh(cherrypy.session['staffer_id']) or is_admin(cherrypy.session['staffer_id']):
                    # print('is actualy dh or admin')
                    try:
                        # load attendee from database or Reggie if not already in DB
                        attend = session.query(Attendee).filter_by(badge_num=params['badge_number']).one()
                        thisorder.attendee_id = attend.public_id
                    except sqlalchemy.orm.exc.NoResultFound:
                        response = shared_functions.lookup_attendee(params['badge_number'])
                        attend = Attendee()
                        attend.badge_num = response['result']['badge_num']
                        attend.public_id = response['result']['public_id']
                        attend.full_name = response['result']['full_name']
                        session.add(attend)
                        thisorder.attendee_id = attend.public_id
                        session.commit()
                else:
                    # currently logged in user is not a DH or admin
                    session.close()
                    raise HTTPRedirect('staffer_meal_list?message=You must be DH or admin to use this feature')
            else:
                # print('not dh_edit')
                thisorder.attendee_id = cherrypy.session['staffer_id']
             
            thisorder.department_id = params['department']
            thisorder.meal_id = save_order  # save order kinda wonky, data will be meal id if 'Submit' is clicked
            thisorder.toggle1 = order_selections(field='toggle1', params=params, is_toggle=True)
            thisorder.toggle2 = order_selections(field='toggle2', params=params, is_toggle=True)
            thisorder.toggle3 = order_selections(field='toggle3', params=params, is_toggle=True)
            thisorder.toppings = order_selections(field='toppings', params=params)
            thisorder.notes = notes
            
            if dh_edit:  # if the order is being created by the DH Edit method, mark overridden so it will be made.
                thisorder.overridden = True
                
            if 'dummydata' in params and params['dummydata']:
                shared_functions.dummy_data(params['dummycount'], thisorder)
            else:
                session.add(thisorder)
                
            session.commit()
            session.close()
            
            raise HTTPRedirect('staffer_meal_list?message=Succesfully saved order')
        
        if order_id:
            # load order
            thisorder = session.query(Order).filter_by(id=order_id).one()
            thismeal = thisorder.meal  # session.query(Meal).filter_by(id=thisorder.meal_id).one()
            
            if dh_edit:
                try:
                    attend = session.query(Attendee).filter_by(badge_num=params['badge_number']).one()
                    allergies = allergy_info(params['badge_number'])
                except sqlalchemy.orm.exc.NoResultFound:
                    response = shared_functions.lookup_attendee(params['badge_number'], full=True)
                    if response['result']['food_restrictions']:
                        allergies = {'standard_labels': response['result']['food_restrictions']['standard_labels'],
                                     'freeform': response['result']['food_restrictions']['freeform']}
                    attend = Attendee()
                    attend.badge_num = response['result']['badge_num']
                    attend.public_id = response['result']['public_id']
                    attend.full_name = response['result']['full_name']
                    session.add(attend)
                    session.commit()
            else:
                attend = session.query(Attendee).filter_by(public_id=cherrypy.session['staffer_id']).one()
                allergies = allergy_info(cherrypy.session['badge_num'])
                
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
            toggles3 = order_split(session, choices=thismeal.toggle3, orders=thisorder.toggle3)
            departments = department_split(session, thisorder.department_id)
            
            template = env.get_template('order_edit.html')
            return template.render(order=thisorder,
                                   meal=thismeal,
                                   attendee=attend,
                                   toppings=toppings,
                                   toggles1=toggles1,
                                   toggles2=toggles2,
                                   toggles3=toggles3,
                                   departments=departments,
                                   messages=messages,
                                   dh_edit=dh_edit,
                                   allergies=allergies,
                                   session=session_info,
                                   c=c)
            
        if meal_id:
            # print('start meal_id')
            # attempt new order from meal_id
            if dh_edit and (is_dh(cherrypy.session['staffer_id']) or is_admin(cherrypy.session['staffer_id'])):
                try:
                    attend = session.query(Attendee).filter_by(badge_num=params['badge_number']).one()
                    allergies = allergy_info(params['badge_number'])
                except sqlalchemy.orm.exc.NoResultFound:
                    response = shared_functions.lookup_attendee(params['badge_number'], full=True)
                    print(response)
                    if response['result']['food_restrictions']:
                        allergies = {'standard_labels': response['result']['food_restrictions']['standard_labels'],
                                     'freeform': response['result']['food_restrictions']['freeform']}
                    attend = Attendee()
                    attend.badge_num = response['result']['badge_num']
                    attend.public_id = response['result']['public_id']
                    attend.full_name = response['result']['full_name']
                    session.add(attend)
                    session.commit()
                    
                try:
                    # check if order already exists, DH edit
                    thisorder = session.query(Order).filter_by(attendee_id=attend.public_id, meal_id=meal_id).one()

                    session.close()
                    raise HTTPRedirect('order_edit?dh_edit=True&badge_number=' + str(params['badge_number']) +
                                       '&order_id=' + str(thisorder.id) +
                                       '&message=An order already exists for this Meal, previously created '
                                       'order selections loaded.')
                except sqlalchemy.orm.exc.NoResultFound:
                    pass
            else:
                try:
                    # check if order already exists, non DH edit
                    thisorder = session.query(Order).filter_by(attendee_id=cherrypy.session['staffer_id'],
                                                               meal_id=meal_id).one()
                    session.close()
                    raise HTTPRedirect('order_edit?order_id=' + str(thisorder.id) +
                                       '&message=An order already exists for this Meal, previously created order '
                                       'selections loaded.')
                except sqlalchemy.orm.exc.NoResultFound:
                    pass
            
            if dh_edit:
                try:
                    attend = session.query(Attendee).filter_by(badge_num=params['badge_number']).one()
                    allergies = allergy_info(params['badge_number'])
                except sqlalchemy.orm.exc.NoResultFound:
                    response = shared_functions.lookup_attendee(params['badge_number'], full=True)
                    if response['result']['food_restrictions']:
                        allergies = {'standard_labels': response['result']['food_restrictions']['standard_labels'],
                                     'freeform': response['result']['food_restrictions']['freeform']}
                    attend = Attendee()
                    attend.badge_num = response['result']['badge_num']
                    attend.public_id = response['result']['public_id']
                    attend.full_name = response['result']['full_name']
                    session.add(attend)
                    session.commit()
                    
            else:
                attend = session.query(Attendee).filter_by(public_id=cherrypy.session['staffer_id']).one()
                allergies = allergy_info(cherrypy.session['badge_num'])

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
            toggles3 = order_split(session, thismeal.toggle3)
            if 'department' in params:
                departments = department_split(session, params['department'])
            else:
                departments = department_split(session)
            thisorder.notes = ''
            
            template = env.get_template('order_edit.html')
            return template.render(order=thisorder,
                                   meal=thismeal,
                                   attendee=attend,
                                   toppings=toppings,
                                   toggles1=toggles1,
                                   toggles2=toggles2,
                                   toggles3=toggles3,
                                   departments=departments,
                                   messages=message,
                                   dh_edit=dh_edit,
                                   allergies=allergies,
                                   session=session_info,
                                   c=c)
        
        # if nothing else matched, not creating, loading, saving, or deleting.  therefore, error.
        raise HTTPRedirect('staffer_meal_list?message=You must specify a meal or order ID to create/edit an order.')
    
    @cherrypy.expose
    @restricted
    def order_delete_confirm(self, order_id='', confirm=False):
        session = models.new_sesh()
        
        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }
        
        thisorder = session.query(Order).filter_by(id=order_id).one()
        
        if confirm:
            if thisorder.attendee_id == cherrypy.session['staffer_id']:
                session.delete(thisorder)
                session.commit()
                session.close()
                raise HTTPRedirect('staffer_meal_list?message=Order Deleted.')
            else:
                session.close()
                raise HTTPRedirect('staffer_meal_list?message=Order does not belong to you?')
        
        template = env.get_template('order_delete_confirm.html')
        return template.render(
            order=thisorder,
            session=session_info,
            c=c
        )

    @cherrypy.expose
    @admin_req
    def meal_delete_confirm(self, meal_id='', confirm=False):
        # todo: something to block malicious users from doctoring links and tricking admins into deleting meals.
        #       perhaps check if meal_delete_confirm is in link at login page?
        
        session = models.new_sesh()
        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }
        
        thismeal = session.query(Meal).filter_by(id=meal_id).one()
    
        if confirm:
            redir = 'meal_setup_list?message=Meal ' + thismeal.meal_name + ' has been Deleted.'
            session.delete(thismeal)
            session.commit()
            session.close()
            raise HTTPRedirect(redir)
        
        session.close()
        
        thismeal.start_time = con_tz(thismeal.start_time)
            
        template = env.get_template('meal_delete_confirm.html')
        return template.render(
            meal=thismeal,
            session=session_info,
            c=c
        )
        
        
    @cherrypy.expose
    @restricted
    def staffer_meal_list(self, message=[], meal_id='', display_all=False, **params):
        """
        Display list of meals staffer is eligible for, unless requested to show all
        """
        # todo: display some information about order status for available meals

        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }
        
        messages = []
        if message:
            text = message
            messages.append(text)
            
        session = models.new_sesh()
        
        eligible = ss_eligible(cherrypy.session['badge_num'])
        
        if not eligible:
            messages.append('You are not scheduled for enough volunteer hours to be eligible for Staff Suite.  '
                            'You will need to get a Department Head to authorize any orders you place.')

        attendee = session.query(Attendee).filter_by(public_id=cherrypy.session['staffer_id']).one()
        
        if 'webhook_url' in params:
            if cherrypy.session['is_dh'] or cherrypy.session['is_admin']:
                # save webhook data
                attendee.webhook_url = params['webhook_url']
                attendee.webhook_data = params['webhook_data']
                session.commit()
                shared_functions.send_webhook(params['webhook_url'], params['webhook_data'])
                junk = attendee.badge_num  # gets SQLAlchemy to reload attendee from database since needed for page display
        
        meals = session.query(Meal).all()
        sorted_shifts, response = combine_shifts(cherrypy.session['badge_num'], no_combine=True, full=True)
        allergies = allergy_info(cherrypy.session['badge_num'])

        meal_display = list()
        
        session.close()
        
        user_exempt = False
        for dept in response['result']['assigned_depts_labels']:
            if dept in cfg.exempt_depts:
                user_exempt = True
            
        now = datetime.utcnow()
        for meal in meals:
            # print("checking meal")
            if cherrypy.session['is_dh'] or user_exempt:
                meal.eligible = True
            else:
                meal.eligible = carryout_eligible(sorted_shifts, meal.start_time, meal.end_time)
            
            if meal.eligible or display_all or meal.order_exists:
                delta = relativedelta(meal.end_time, now)
                # rd is negative if first item is before second
                rd = 0
                rd += delta.minutes
                rd += delta.hours * 60
                rd += delta.days * 1440
                # hides meals in the past by default
                if rd >= 0 or display_all:
                    meal_display.append(meal)
        
        if len(meal_display) == 0:
            messages.append('You are not signed up for any shifts that overlap with meal times. '
                            'If you work in a non-shift capacity, please click the "Show all meals" button below '
                            'to submit a carryout order.')
        
        for thismeal in meals:
            thismeal.start_time = con_tz(thismeal.start_time)
            thismeal.end_time = con_tz(thismeal.end_time)
            thismeal.cutoff = con_tz(thismeal.cutoff)
            try:
                orders = session.query(Order).filter_by(meal_id=thismeal.id,
                                                           attendee_id=cherrypy.session['staffer_id']).all()
                # print('0------------------printing matching orders-----------------')
                # for order in orders:
                    # print(str(order.meal_id) + ', ' + str(order.id))
                # todo: more efficient code for this, I think there's a way to load orders for all meals in one query request
                thisorder = session.query(Order).filter_by(meal_id=thismeal.id,
                                                           attendee_id=cherrypy.session['staffer_id']).one()
                thismeal.order_exists = True
                if thisorder.overridden:
                    thismeal.overridden = True
            except sqlalchemy.orm.exc.NoResultFound:
                pass
            
        template = env.get_template('staffer_meal_list.html')
        return template.render(messages=messages,
                               meallist=meal_display,
                               allergies=allergies,
                               attendee=attendee,
                               session=session_info,
                               c=c)
            
    @cherrypy.expose
    @admin_req
    def config(self, badge='', message=[], dangerous=False, delete_order='', **params):
        messages = []

        if message:
            text = message
            messages.append(text)

        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }
        
        if delete_order:
            session = models.new_sesh()
            thisorder = session.query(Order).filter_by(id=delete_order).one()
            session.delete(thisorder)
            session.commit()
            session.close()
            raise HTTPRedirect('config?dangerouse=true&message=order ' + delete_order + ' deleted.')
        
        if 'radio_select_count' in params:
            # save config
            
            admin_list = params['admin_list']
            staffer_list = params['staffer_list']
            exempt_depts = params['exempt_depts']
            
            if 'local_print' in params:
                cfg.local_print = True
            else:
                cfg.local_print = False
            if 'remote_print' in params:
                cfg.remote_print = True
            else:
                cfg.remote_print = False
            cfg.multi_select_count = int(params['multi_select_count'])
            cfg.radio_select_count = int(params['radio_select_count'])
            # cfg.schedule_tolerance = int(params['schedule_tolerance'])
            cfg.date_format = params['date_format']
            cfg.ss_hours = int(params['ss_hours'])
            # print(params['staffer_list'])
            
            if 'staff_barcode' in params and params['staff_barcode']:
                # print('----------------------staff_barcode----------------------')
                shared_functions.add_access(params['staff_barcode'], 'staff')
                staffer_list = ',\n'.join(cfg.staffer_list)
            if 'admin_barcode' in params and params['admin_barcode']:
                # print('----------------------admin_barcode----------------------')
                shared_functions.add_access(params['admin_barcode'], 'admin')
                admin_list = ',\n'.join(cfg.admin_list)
            manager_list = ',\n'.join(cfg.food_managers)
                
            cfg.save(admin_list, staffer_list, exempt_depts, manager_list)
            
            raise HTTPRedirect('config?message=Successfully saved config settings')

        # load lists into plain string for webpage
        admin_list = ',\n'.join(cfg.admin_list)
        staffer_list = ',\n'.join(cfg.staffer_list)
        exempt_depts = ',\n'.join(cfg.exempt_depts)

        if badge:
            # print('------------looking up attendee------------------')
            attendee = shared_functions.lookup_attendee(badge, True)
            attendee = json.dumps(attendee, indent=2)
            # print(attendee)
            template = env.get_template('config.html')
            return template.render(messages=messages,
                                   session=session_info,
                                   admin_list=admin_list,
                                   staffer_list=staffer_list,
                                   exempt_depts=exempt_depts,
                                   dangerous=True,
                                   attendee=attendee,
                                   c=c,
                                   cfg=cfg)
        
        template = env.get_template('config.html')
        return template.render(messages=messages,
                               session=session_info,
                               admin_list=admin_list,
                               staffer_list=staffer_list,
                               exempt_depts=exempt_depts,
                               dangerous=dangerous,
                               c=c,
                               cfg=cfg)

    @cherrypy.expose
    @admin_req
    def dangerous(self, reset_dept_list=False, reset_checkin_list=False):
        """
        For hidden buttons to do potentially very dangerous things
        """
        session = models.new_sesh()
        
        if reset_dept_list:
            depts = session.query(Department).all()
            for dept in depts:
                session.delete(dept)
            session.commit()
            shared_functions.load_departments()
        
        if reset_checkin_list:
            checkins = session.query(Checkin).all()
            for checkin in checkins:
                session.delete(checkin)
            session.commit()
        
        session.close()
        raise HTTPRedirect("config")
    
    @cherrypy.expose
    @dh_or_admin
    def dept_order_selection(self, message='', **params):
        """
        Allows DH to select meal time and which department they wish to view the dept_order for.
        Filters meal list to only show future meals by default (by end time, not start time)
        Filters selectable departments to only include ones the DH is assigned to unless user is Admin
        """
        messages = []
        if message:
            text = message
            messages.append(text)

        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }
        
        # meal_id would be present if Select button is clicked, sends to selected dept_order
        if 'meal_id' in params:
            raise HTTPRedirect('dept_order?meal_id=' + str(params['meal_id']) + '&dept_id=' + str(params['dept_id']))
        
        session = models.new_sesh()
        departments = department_split(session)
        
        # todo: filter by future meals, by end time of meal
        meal_list = session.query(Meal).all()
        
        for meal in meal_list:
            meal.start_time = con_tz(meal.start_time)
            meal.end_time = con_tz(meal.end_time)
            meal.cutoff = con_tz(meal.cutoff)
            
        session.close()
        template = env.get_template("dept_order_selection.html")
        return template.render(depts=departments,
                               meals=meal_list,
                               session=session_info,
                               messages=messages,
                               c=c)
        

    @cherrypy.expose
    @dh_or_admin
    def dept_order(self, meal_id, dept_id, skip=False, message="", **params):
        """
        Usable by Department Heads and admins
        list of orders for selected meal and department
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

        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer'],
            'is_food_manager': cherrypy.session['is_food_manager']
        }
        
        if 'order_badge' in params:
            raise HTTPRedirect('order_edit?dh_edit=True&meal_id=' + str(meal_id) + '&badge_number=' +
                               str(params['order_badge']) + '&department=' + str(params['order_department']))
        
        if 'food_manager' in params:
            success = shared_functions.add_access(params['food_manager'], 'food_manager')
            if success:
                raise HTTPRedirect('dept_order?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                                   '&skip=true&message=Food Manager Succesfully Added')
            else:
                session = models.new_sesh()
                attend = session.query(Attendee).filter_by(badge_num=params['food_manager']).one()
                if attend.public_id in cfg.food_managers:
                    raise HTTPRedirect('dept_order?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                                       '&skip=true&message=Food Manager already added to list')
                else:
                    raise HTTPRedirect('dept_order?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                                       '&skip=true&message=Error adding food manager')
        
        session = models.new_sesh()
        
        dept = session.query(Department).filter_by(id=dept_id).one()
        
        # send DH to page for setting default contact info.
        # DH will be able to skip, but every time the come back to the Dept Order page it will redirect again.
        # hopefully this will result in people filling this out with useful info rather than putting trash.
        if not skip:
            if not dept.slack_channel and not dept.slack_contact and not dept.other_contact and not dept.text_contact \
                    and not dept.email_contact:
                session.close()
                raise HTTPRedirect('dept_contact?dept_id=' + str(dept_id) +
                                   '&message=Please add default contact info for your department.  '
                                   'This will be used when beginning new meal bundles for your department '
                                   'and for meals where no other contact info is specified.' +
                                   '&original_location=dept_order%3Fdept_id%3D' +
                                   str(dept_id) + '%26meal_id%3D' + str(meal_id))
        
        thismeal = session.query(Meal).filter_by(id=meal_id).one()
        
        # tries to load existing dept order, if none creates a new one.
        try:
            this_dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            this_dept_order = create_dept_order(dept_id, meal_id, session)
            this_dept_order.slack_channel = dept.slack_channel
            this_dept_order.slack_contact = dept.slack_contact
            this_dept_order.other_contact = dept.other_contact
            #this_dept_order.text_contact = dept.text_contact
            #this_dept_order.email_contact = dept.email_contact
            
            session.commit()
            # reload order since commit flushes it from cache (apparently)
            this_dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()
            thismeal = session.query(Meal).filter_by(id=meal_id).one()
            dept = session.query(Department).filter_by(id=dept_id).one()
        
        if 'other_contact' in params or 'slack_channel' in params or 'text_contact' in params or 'email_contact' in params:
            # save changes to dept_order
            this_dept_order.slack_channel = params['slack_channel']
            this_dept_order.slack_contact = params['slack_contact']
            this_dept_order.other_contact = params['other_contact']
            
            session.commit()
            # reload these items since commit flushes them
            dept = session.query(Department).filter_by(id=dept_id).one()
            thismeal = session.query(Meal).filter_by(id=meal_id).one()
            this_dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()
            
            messages.append('Department order contact info successfully updated.')

        order_list = session.query(Order).filter_by(meal_id=meal_id, department_id=dept_id).options(
            subqueryload(Order.attendee)).all()
        # todo: check each order to see if the attendee is eligible for this meal, highlight in html if not
        for order in order_list:
            # print("checking meal")
            sorted_shifts = combine_shifts(order.attendee.badge_num, no_combine=True)
            if is_dh(order.attendee_id):
                order.eligible = True
            else:
                order.eligible = carryout_eligible(sorted_shifts, thismeal.start_time, thismeal.end_time)
            
        if len(order_list) == 0:
            messages.append('Your department does not have any orders for this meal.')

        thismeal.start_time = con_tz(thismeal.start_time)
        thismeal.end_time = con_tz(thismeal.end_time)
        thismeal.cutoff = con_tz(thismeal.cutoff)
        
        session.close()
        
        if this_dept_order.started:
            this_dept_order.start_time = con_tz(this_dept_order.start_time).strftime(cfg.date_format)
        if this_dept_order.completed:
            this_dept_order.completed_time = con_tz(this_dept_order.completed_time).strftime(cfg.date_format)

        departments = department_split(session, dept_id)
            
        template = env.get_template('dept_order.html')
        return template.render(dept=dept,
                               orders=order_list,
                               dept_order=this_dept_order,
                               meal=thismeal,
                               departments=departments,
                               messages=messages,
                               session=session_info,
                               c=c)
        
    @cherrypy.expose
    @dh_or_admin
    def order_override(self, order_id, meal_id, dept_id, remove_override=False):
        """
        Override or remove override on an order
        """
        session = models.new_sesh()
        dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()
        # todo: check for if order started or completed for admin user and do extra warnings?
        if dept_order.started and not cherrypy.session['is_admin']:
            session.close()
            raise HTTPRedirect('dept_order_selection?message=The order for your department for this meal has already been started.')
        order = session.query(Order).filter_by(id=order_id).options(subqueryload(Order.attendee)).one()
        if remove_override:
            order.overridden = False
            message = 'Override removed for ' + str(order.attendee.badge_num)
        else:
            order.overridden = True
            message = 'Override added for ' + str(order.attendee.badge_num)
        session.commit()
        session.close()
        raise HTTPRedirect('dept_order?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                           '&message=' + message + str(cherrypy.session['badge_num']))
           
    
    @cherrypy.expose
    @ss_staffer
    def ssf_meal_list(self, display_all=False):
        """
        Displays list of Meals to be fulfilled
        """
        
        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }
        
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
            """ removed during testing cause West is in past
            rd = relativedelta(meal.end_time + shift_buffer, now)
            # skips adding to list if item is in past
            
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
                               session=session_info,
                               c=c)

    @cherrypy.expose
    @ss_staffer
    def ssf_dept_list(self, meal_id):
        """
        For chosen meal, shows list of departments with how many orders are currently submitted for that department
        Fulfilment staff can select a department to view order details.
        """
        
        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }
        
        session = models.new_sesh()
        
        depts = session.query(models.department.Department).all()
        dept_list = list()
        completed_depts = list()
        total_orders = 0
        remaining_orders = 0
        
        for dept in depts:
            count = session.query(Order).filter_by(department_id=dept.id, meal_id=meal_id).count()
            
            try:
                dept_order = session.query(DeptOrder).filter_by(dept_id=dept.id, meal_id=meal_id).one()
            except sqlalchemy.orm.exc.NoResultFound:
                dept_order = create_dept_order(dept.id, meal_id, session)
                
            if not dept_order.completed:
                dept_list.append((dept.name, count, dept.id))
                remaining_orders += count
            else:
                completed_depts.append((dept.name, count, dept.id))
                
            total_orders += count
        
        # print(dept_list)
        session.close()
        template = env.get_template('ssf_dept_list.html')
        return template.render(depts=dept_list,
                               completed_depts=completed_depts,
                               meal_id=meal_id,
                               total=total_orders,
                               remaining=remaining_orders,
                               session=session_info,
                               c=c)
        
        
    @cherrypy.expose
    @ss_staffer
    def ssf_orders(self, meal_id, dept_id, message=[]):
        """
        Shows list of orders for selected meal and dept.
        Has buttons to lock order for fulfilment, or if already locked by mistake to unlock.
        Once order is locked buttons to print all orders or individual orders become available
        Button to mark department order complete - notifies departments it's ready for pickup
        """
        
        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }

        messages = []
        if message:
            text = message
            messages.append(text)

        session = models.new_sesh()
        try:
            dept_order = session.query(DeptOrder).filter_by(dept_id=dept_id, meal_id=meal_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            dept_order = create_dept_order(dept_id, meal_id, session)
        
        orders = session.query(Order).filter_by(department_id=dept_id, meal_id=meal_id)\
            .options(joinedload(Order.attendee)).all()
        
        thismeal = session.query(Meal).filter_by(id=meal_id).one()
        
        dept = session.query(Department).filter_by(id=dept_id).one()
        dept_name = dept.name
        
        session.close()  # this has to be before the order loop below.  don't know why, seems like it should be after.
        
        order_list = list()
        print('-------------------orders list-------------------')
        print(orders)
        for order in orders:
            sorted_shifts, response = combine_shifts(order.attendee.badge_num, full=True, no_combine=True)
            print('-------------------eligibility code starts--------------------')
            if response['result']['is_dept_head']:
                order.eligible = True
                print('----------------eligible by being DH----------------')
            else:
                for dept in response['result']['assigned_depts_labels']:
                    if dept in cfg.exempt_depts:
                        order.eligible = True
                        print('---------------------------eligible by being in exempt dept-------------------')
                if not order.eligible:  # checks for exempt dept first, then if not exempt checks shifts
                    order.eligible = carryout_eligible(sorted_shifts, thismeal.start_time, thismeal.end_time)
            # if not eligible and not overridden, remove from list for display/printing
            
            order.toggle1 = return_selected_only(session, choices=thismeal.toggle1, orders=order.toggle1)
            order.toggle2 = return_selected_only(session, choices=thismeal.toggle2, orders=order.toggle2)
            order.toggle3 = return_selected_only(session, choices=thismeal.toggle3, orders=order.toggle3)
            order.toppings = return_not_selected(session, choices=thismeal.toppings, orders=order.toppings)

            if response['result']['food_restrictions']:
                order.allergies = {'standard_labels': response['result']['food_restrictions']['standard_labels'],
                                   'freeform': response['result']['food_restrictions']['freeform']}
            if order.eligible or order.overridden:
                print('------------appending ordering-------------')
                order_list.append(order)
                
        orders = order_list
        
        if dept_order.started:
            dept_order.start_time = con_tz(dept_order.start_time).strftime(cfg.date_format)
            # generate labels
            if cfg.local_print:
                labels = env.get_template('print_labels2.html')
                options = {
                    'page-height': '2.0in',
                    'page-width': '4.0in',
                    'margin-top': '0.0in',
                    'margin-right': '0.0in',
                    'margin-bottom': '0.0in',
                    'margin-left': '0.0in',
                    #'encoding': "UTF-8",
                    #'print-media-type': None,
                    'dpi': '203'
                }
                
                # / in name confuses the pdf creator when it tries to save the file
                dept_name.replace('/', '-')
                dept_name.replace('\\', '-')

                if cfg.devenv:  # todo: change this to detect OS instead
                    # for some reason the silly system decided to not find it automatically anymore
                    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
                    config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
                    
                    rendered_labels = labels.render(orders=orders,
                                                    meal=thismeal,
                                                    dept_name=dept_name)
                    
                    pdfkit.from_string(rendered_labels,
                                       'pdfs\\' + dept_name + '.pdf',
                                       options=options,
                                       configuration=config)
                else:
                    #path_wkhtmltopdf = r'/usr/local/bin/wkhtmltopdf'
                    #config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
                    pdfkit.from_string(labels.render(orders=orders,
                                                     meal=thismeal,
                                                     dept_name=dept_name),
                                       'pdfs/' + dept_name + '.pdf',
                                       options=options)
        if dept_order.completed:
            dept_order.completed_time = con_tz(dept_order.completed_time).strftime(cfg.date_format)
        
        template = env.get_template('ssf_orders.html')
        return template.render(dept_order=dept_order,
                               dept_name=dept_name,
                               dept_id=dept_id,
                               order_list=orders,
                               meal=thismeal,
                               messages=messages,
                               session=session_info,
                               c=c)
    
    @cherrypy.expose
    @ss_staffer
    def ssf_lock_order(self, meal_id, dept_id, unlock_order=False):
        """
        Locks or unlocks dept_order and individual orders for selected meal and department
        """
        session = models.new_sesh()
        dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()
        orders = session.query(Order).filter_by(meal_id=meal_id, department_id=dept_id).all()

        if not unlock_order:
            dept_order.started = True
            dept_order.start_time = now_utc()
            for order in orders:
                order.locked = True
            session.commit()
            session.close()
            raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                               '&message=This Bundle is now locked.')
        else:
            if dept_order.completed:
                session.close()
                raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                                   '&message=You cannot un-lock an Bundle that is marked Completed.')
            
            dept_order.started = False
            dept_order.start_time = None
            for order in orders:
                order.locked = False
            session.commit()
            session.close()
            raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                               '&message=This Bundle is now un-locked.')
        
    @cherrypy.expose
    @ss_staffer
    def ssf_complete_order(self, meal_id, dept_id, uncomplete_order=False):
        """
        Marks or unmarks department order as complete for selected meal and department
        """
        session = models.new_sesh()
        dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()
        
        if not uncomplete_order:
            if not dept_order.started:
                session.close()
                raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                                   '&message=The Bundle must be Locked before it can be marked Complete.')
            dept_order.completed = True
            dept_order.completed_time = now_utc()
            dept = session.query(Department).filter_by(id=dept_id).one()
            
            if dept_order.slack_channel:
                message = 'Your food order bundle for ' + dept.name + ' ' \
                          'is ready, please pickup from Staff Suite.  ' + now_contz().strftime(cfg.date_format) + \
                          '  ' + dept_order.slack_contact
                slack_bot.send_message(dept_order.slack_channel, message)
                
            orders = session.query(Order).filter_by(department_id=dept_order.dept_id, meal_id=dept_order.meal_id) \
                .options(subqueryload(Order.attendee)).all()
            for order in orders:
                if order.attendee.webhook_url:
                    shared_functions.send_webhook(order.attendee.webhook_url, order.attendee.webhook_data)
                
            if dept_order.other_contact:
                session.commit()
                session.close()
                raise HTTPRedirect('dept_order_details?dept_order_id=' + str(dept_order.id) +
                                   '&message=This department has requested manual contact.  '
                                   'Please contact them as listed in the Other Contact Info box.')
            session.commit()
            session.close()
            raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                               '&message=This Bundle is now marked Complete.')
        else:
            dept_order.completed = False
            dept_order.completed_time = None
            session.commit()
            session.close()
            raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                               '&message=This Bundle is now un-marked Complete.')

    @dh_or_staffer
    @cherrypy.expose
    def dept_order_details(self, dept_order_id, **params):
        """
        Displays contact info details for a dept's order
        :param dept_order_id:
        :param original_location:
        :return:
        """

        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }

        session = models.new_sesh()
        dept_order = session.query(DeptOrder).filter_by(id=dept_order_id).one()
        
        if 'slack_channel' in params:
            # save record
            dept_order.slack_contact = params['slack_contact']
            dept_order.slack_channel = params['slack_channel']
            #dept_order.text_contact = params['text_contact']
            #dept_order.email_contact = params['email_contact']
            dept_order.other_contact = params['other_contact']
            session.commit()
            session.close()
            raise HTTPRedirect('dept_order_details?dept_order_id=' + str(dept_order_id))
        
        # load record
        meal = session.query(Meal).filter_by(id=dept_order.meal_id).one()
        dept = session.query(Department).filter_by(id=dept_order.dept_id).one()
        session.close()
        template = env.get_template('dept_order_details.html')
        return template.render(dept_order=dept_order,
                               meal=meal,
                               dept=dept.name,
                               session=session_info,
                               c=c)
    
    @dh_or_staffer
    @cherrypy.expose
    def dept_contact(self, dept_id, original_location=None, **params):
        """
        Displays and allows updating of Department's default contact info
        :param dept_order_id:
        :param original_location:
        :return:
        """
        
        session_info = {
            'is_dh': cherrypy.session['is_dh'],
            'is_admin': cherrypy.session['is_admin'],
            'is_ss_staffer': cherrypy.session['is_ss_staffer']
        }

        original_location = shared_functions.create_valid_user_supplied_redirect_url(original_location,
                                                                                     default_url='staffer_meal_list')
        session = models.new_sesh()
        dept = session.query(Department).filter_by(id=dept_id).one()
        
        if 'slack_channel' in params:
            # save record
            dept.slack_contact = params['slack_contact']
            dept.slack_channel = params['slack_channel']
            #dept.text_contact = params['text_contact']
            #dept.email_contact = params['email_contact']
            dept.other_contact = params['other_contact']
            
            dept_orders = session.query(DeptOrder).filter_by(dept_id=dept_id).all()
            for do in dept_orders:
                # finds dept orders with blank contact info and fills their default contact info
                if not do.slack_channel and not do.slack_contact and not do.other_contact and not do.text_contact \
                        and not do.email_contact:
                    do.slack_contact = dept.slack_contact
                    do.slack_channel = dept.slack_channel
                    do.other_contact = dept.other_contact
                    #do.text_contact = dept.text_contact
                    #do.email_contact = dept.email_contact
            
            session.commit()
            session.close()
            raise HTTPRedirect(original_location)
            
        session.close()
        template = env.get_template('dept_contact.html')
        return template.render(dept=dept,
                               original_location=original_location,
                               session=session_info,
                               c=c)

    @cherrypy.expose
    @admin_req
    def create_checkin_csv(self):
        """
        creates a .csv file with data from the eat-in checkins
        """
        session = models.new_sesh()
    
        checkins = session.query(models.checkin.Checkin).all()
        
        export = 'Meal ID,Meal Desc,Badge Number,Timestamp\n'
        for checkin in checkins:
            if checkin.meal_id:
                export += str(checkin.meal_id)
                export += ','
                export += checkin.meal.description
            else:
                export += ','
                export += 'non-meal period'
            export += ','
            export += str(checkin.attendee.badge_num)
            export += ','
            export += checkin.timestamp.strftime(cfg.date_format)
            export += '\n'
        
        exportfile = open('checkin_export.csv', 'w')
        exportfile.write(export)
        exportfile.close()
        
        session.close()
        raise HTTPRedirect('config?message=Succesfully exported checkins csv')

    @cherrypy.expose
    @admin_req
    def create_orders_csv(self):
        """
        Creates a .csv file with data from the carryout orders
        """
        session = models.new_sesh()
        start = datetime.utcnow()
        orders = session.query(models.order.Order).all()
        export = 'Meal Id,Meal Desc,Department,Badge Number,Overridden,Eligible for Carryout,Notes\n'
        print('-------------beginning order CSV export-------------')
        for order in orders:
            export += str(order.meal_id)
            export += ','
            export += order.meal.description
            export += ','
            export += order.department.name
            export += ','
            export += str(order.attendee.badge_num)
            export += ','
            export += str(order.overridden)
            export += ','
            shifts = combine_shifts(order.attendee.badge_num, no_combine=True)
            export += str(shared_functions.carryout_eligible(shifts, order.meal.start_time, order.meal.end_time))
            export += ','
            export += order.notes
            export += '\n'
        
        end = datetime.utcnow()
        rd = relativedelta(start, end)
        print('-------------done pulling orders--------------')
        print('minutes ' + str(rd.minutes))
        print('seconds ' + str(rd.seconds))
        
        exportfile = open('order_export.csv', 'w', encoding='utf-8')
        exportfile.write(export)
        exportfile.close()

        session.close()
        raise HTTPRedirect('config?message=succesfully exported orders report')