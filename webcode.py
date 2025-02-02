# sections of this are copied from https://github.com/magfest/ubersystem/blob/master/uber/site_sections/signups.py
# then modified for my needs.
import json
from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal

import pdfkit
import pytz
import re
from sqlalchemy import desc
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
from models.slack_user import Slack_User
import shared_functions
from shared_functions import api_login, HTTPRedirect, order_split, order_selections, allergy_info, \
                     meal_join, meal_split, meal_blank_toppings, department_split, create_dept_order, \
                     ss_eligible, carryout_eligible, combine_shifts, return_selected_only, return_not_selected, \
                     con_tz, utc_tz, now_utc, now_contz, is_admin, is_ss_staffer, is_dh, is_super_admin, \
                     get_session_info, get_vip_list, is_vip
import slack_bot


class Root:

    @restricted
    @cherrypy.expose
    def index(self, **kwargs):
        raise HTTPRedirect('staffer_meal_list')

    @cherrypy.expose
    def login(self, message=[], first_name='', last_name='',
              email='', zip_code='', original_location=None, logout=False):
        """
        Login Screen.  Can redirect to original destination.
        :param message: list of messages to display on screen.  can be empty
        :param first_name:
        :param last_name:
        :param email:
        :param zip_code:
        :param original_location: original location person was attempting to reach when redirected to login screen
        :param logout: if True expires user session
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

        # if login from returns data for all fields, send login request to Uber
        if first_name and last_name and email and zip_code:
            response = api_login(first_name=first_name, last_name=last_name,
                                 email=email, zip_code=zip_code)

            if 'error' in response:
                messages.append(response['error']['message'])
                error = True
                print(response['error']['message'])

            if not error:
                # ensure_csrf_token_exists()  this is commented out cause I haven't yet learned what/how for CSRF
                cherrypy.session['staffer_id'] = str(response['result']['public_id']) # this one is for when attendee search works with Uber public ID
                # cherrypy.session['staffer_id'] = str(response['result']['badge_num']) # this one is for when attendee search is not accepting public ID, uses just badge number everywhere instead
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

                if is_super_admin(cherrypy.session['staffer_id']):
                    cherrypy.session['is_super_admin'] = True
                else:
                    cherrypy.session['is_super_admin'] = False

                # food manager tag is for a person who only has this specific privilige, not DH or admin also.
                # This is not added to DH because food manager is basically a DH minus adding other food managers.
                if cherrypy.session['staffer_id'] in cfg.food_managers and not cherrypy.session['is_dh'] \
                        and not cherrypy.session['is_admin']:
                    cherrypy.session['is_food_manager'] = True
                    cherrypy.session['is_dh'] = True
                else:
                    cherrypy.session['is_food_manager'] = False

                # check if orders open
                if not cfg.orders_open():
                    if not cherrypy.session['is_ss_staffer']:
                        print("not staffer")
                        if not cherrypy.session['is_admin']:
                            print("not admin")
                            if not cherrypy.session['is_dh']:
                                print("not dh")
                                if not cherrypy.session['is_food_manager']:
                                    print("not food manager")
                                    print(response['result']['badge_type_label'])
                                    if response['result']['badge_type_label'] == 'Staff' and cfg.early_login_enabled:
                                        pass
                                    else:
                                        raise HTTPRedirect('login?message=Orders are not yet open.  '
                                                           'You can login beginning at '
                                                           + con_tz(c.EPOCH).strftime(cfg.date_format) + ' ID: ' +
                                                           str(cherrypy.session['staffer_id']))

                session = models.new_sesh()
                # add or update attendee record in DB
                try:
                    attendee = session.query(Attendee).filter_by(public_id=str(cherrypy.session['staffer_id'])).one()

                    # only update record if different
                    if not attendee.full_name == response['result']['full_name'] \
                            or not attendee.badge_num == response['result']['badge_num']:
                        attendee.full_name = response['result']['full_name']
                        attendee.badge_num = response['result']['badge_num']
                        session.commit()

                except sqlalchemy.orm.exc.NoResultFound:
                    # new attendee login, creating record
                    attendee = Attendee()
                    attendee.badge_num = response['result']['badge_num']
                    attendee.public_id = cherrypy.session['staffer_id']
                    attendee.full_name = response['result']['full_name']
                    session.add(attendee)
                    session.commit()

                session.close()

                raise HTTPRedirect(original_location)

        # if not an active login attempt, load login page
        template = env.get_template('login.html')
        if not cfg.env == "prod":
            isdev = True
        else:
            isdev = False
        return template.render(messages=messages,
                               first_name=first_name,
                               last_name=last_name,
                               email=email,
                               zip_code=zip_code,
                               original_location=original_location,
                               c=c,
                               cfg=cfg,
                               isdev=isdev)

    @cherrypy.expose
    @admin_req
    def meal_setup_list(self, message=None, meal_id=''):

        messages = []
        if message:
            text = message
            messages.append(text)

        session = models.new_sesh()

        # this should be triggered if an edit button is clicked from the list
        if meal_id:
            session.close()
            raise HTTPRedirect('meal_edit?meal_id=' + meal_id)

        meallist = session.query(Meal).order_by(models.meal.Meal.start_time).all()
        session.close()

        for meal in meallist:
            meal.start_time = con_tz(meal.start_time)

        session_info = get_session_info()

        template = env.get_template('meal_setup_list.html')
        return template.render(messages=messages,
                               meallist=meallist,
                               session=session_info,
                               c=c,
                               cfg=cfg)

    @cherrypy.expose
    @ss_staffer
    def dinein_checkin(self):
        """
        This page handles scanning attendee's badges for walk-in food
        """
        session = models.new_sesh()
        now = now_utc()
        current_meals = session.query(Meal).filter(Meal.start_time < now, Meal.end_time > now).order_by(Meal.end_time).all()
        if not current_meals:
            current_meal = None
        else:
            current_meal = current_meals[-1]
        session.close()

        template = env.get_template("dinein_checkin.html")

        session_info = get_session_info()

        return template.render(current_meal=current_meal,
                               c=c,
                               cfg=cfg,
                               session=session_info)

    @cherrypy.expose
    @ss_staffer
    def checkin_badge(self, badge=''):
        """
        Processes checkin requests for walk-ins
        """
        badge = badge.replace('plussign', '+')
        # remove accidental whitespace
        badge = badge.strip()

        # if badge is blank
        if not badge:
            return json.dumps({"success": False, "badge": badge, "reason": "scan field blank?"})

        # barcode on badges starts with ~
        if badge[0] == "~":
            badge = shared_functions.barcode_to_badge(badge)

        else:
            try:
                badge = int(badge)
            except ValueError:
                return json.dumps({"success": False, "badge": badge, "reason": "Not a number?"})

        # badge will be none if lookup fails
        if not badge:
            return json.dumps({"success": False, "badge": '', "reason": "Could not locate badge."})
        session = models.new_sesh()
        now = now_utc()
        meal = session.query(Meal).filter(Meal.start_time < now, Meal.end_time > now).order_by(Meal.end_time).one_or_none()

        try:
            attend = session.query(Attendee).filter_by(badge_num=badge).one()

            print(attend.public_id)
            print(attend.badge_num)
            print(attend.full_name)
            # checks if attendee already in DB
        except sqlalchemy.orm.exc.NoResultFound:
            response = shared_functions.lookup_attendee(badge)
            if 'error' in response:
                session.close()
                return json.dumps({"success": False, "badge": badge, "reason": "Badge # {} is not found in Reggie".format(badge)})

            try:
                attendee = session.query(Attendee).filter_by(public_id=response['result']['public_id']).one()
                attendee.badge_num = response['result']['badge_num']
                attendee.public_id = response['result']['public_id']
                attendee.full_name = response['result']['full_name']

            except sqlalchemy.orm.exc.NoResultFound:
                attend = Attendee()
                attend.badge_num = response['result']['badge_num']
                attend.public_id = response['result']['public_id']
                attend.full_name = response['result']['full_name']
                session.add(attend)
                session.commit()
        except sqlalchemy.exc.MultipleResultsFound:
            messageforslack = "Someone's Checkin lookup retured multiple badges somehow.  " + str(badge)
            slack_bot.send_message("@wombat3", messageforslack)
            session.close()
            return json.dumps(
                {"success": False, "badge": badge, "reason": "Found multiple matching badges?".format(badge)})

        if meal:
            # check for existing carryout order for this meal period
            order = session.query(Order).filter(Order.attendee_id == attend.public_id,
                                                Order.meal_id == meal.id).one_or_none()
            if order:
                sorted_shifts, response = combine_shifts(attend.badge_num, full=True, no_combine=True)
                eligible = carryout_eligible(sorted_shifts, response, meal.start_time, meal.end_time)

                # if during meal period and order exists for this attendee and meal period
                # their order is eligible for carryout, they get kicked out
                if eligible or order.overridden:
                    session.close()
                    return json.dumps({"success": False, "badge": badge, "reason": "Attendee has placed a delivery "
                                                                                   "order for this meal.  Do they need "
                                                                                   "to pick it up?".format(badge)})

        has_allergy = False
        allergies = allergy_info(badge)
        if len(allergies['standard_labels']) > 0:
            has_allergy = True
        if allergies['freeform']:
            has_allergy = True

        # loads any prior checkins this event, by current meal period if during meal period
        if meal:
            checkin = session.query(Checkin).filter(Checkin.attendee_id == attend.public_id,
                                                    Checkin.meal_id == meal.id).all()
        else:
            checkin = session.query(Checkin).filter(Checkin.attendee_id == attend.public_id,
                                                    Checkin.meal_id == None).order_by(desc(Checkin.timestamp)).all()
        if checkin and meal:
            # ie if there is a checkin for this meal period (meal is blank if not during meal period)
            checkin = Checkin(attendee_id=attend.public_id, meal_id=meal.id, duplicate=True)
            session.add(checkin)
            session.commit()
            session.close()
            # Attendee is already checked in for this meal.
            return json.dumps({"success": True, "badge": badge,
                               "reason": "Checked in successfully!",
                               "has_allergy": has_allergy})

        if not shared_functions.ss_eligible(badge):
            session.close()
            return json.dumps({"success": False, "badge": badge,
                               "reason": "Attendee is not eligible for Staff Suite by normal rules. "
                                         "Are we letting people in anyway?",
                               "has_allergy": has_allergy})

        if meal:
            # if during a meal period and not already a checkin for this meal period
            # checks if there is an existing meal associated checkin above
            checkin = Checkin(attendee_id=attend.public_id, meal_id=meal.id)
        else:
            if checkin:
                # if not during meal period, and one or more checkins for this attendee this event.
                for item in checkin:
                    delta = relativedelta(item.timestamp, datetime.utcnow())
                    if abs(delta.minutes) <= 15 and delta.hours == 0 and abs(delta.days) == 0:
                        # if a previously received checkin
                        # is within 15 minutes of current checkin, does not record as another checkin
                        checkin = Checkin(attendee_id=attend.public_id, meal_id=None, duplicate=True)
                        session.add(checkin)
                        session.commit()
                        session.close()
                        # Attendee is already checked in.
                        return json.dumps({"success": True, "badge": badge, "reason": "Checked in successfully!",
                                           "has_allergy": has_allergy})
            # if no existing checkin for this attendee overlaps current time, create new checkin
            checkin = Checkin(attendee_id=attend.public_id, meal_id=None)

        # save new checkin record to DB
        session.add(checkin)
        session.commit()
        session.close()
        return json.dumps({"success": True, "badge": badge, "reason": "Checked in successfully!",
                           "has_allergy": has_allergy})

    @cherrypy.expose
    @admin_req
    def manage_vip(self, vip_list=False):
        """
        Displays VIP list, allows adding new VIPs
        """

        if vip_list:
            parts = vip_list.split(',')
            session = models.new_sesh()

            vip = session.query(models.attendee.Attendee).filter_by(badge_num=parts[0]).one()
            vip.is_vip = False
            session.commit()
            session.close()

        session_info = get_session_info()

        template = env.get_template("manage_vip.html")
        return template.render(vips=get_vip_list(),
                               session=session_info,
                               c=c,
                               cfg=cfg)

    @cherrypy.expose
    @admin_req
    def add_vip(self, badge='', firstload=False):
        """
        Attempts to add badge# or barcode to VIPs list
        """
        if firstload:
            return json.dumps({"success": True, "badge": badge,
                               "reason": "Loading VIPs list",
                               "vips": get_vip_list()})
        if badge[0] == "~":
            badge = shared_functions.barcode_to_badge(badge)
        else:
            try:
                badge = int(badge)
            except ValueError:
                return json.dumps({"success": False, "badge": badge, "reason": "Not a number?",
                                   "vips": get_vip_list()})

        if not badge:
            return json.dumps({"success": False, "badge": badge, "reason": "Could not locate badge.",
                               "vips": get_vip_list()})

        session = models.new_sesh()

        try:
            attend = session.query(Attendee).filter_by(badge_num=badge).one()
            # checks if attendee already in DB
        except sqlalchemy.orm.exc.NoResultFound:
            response = shared_functions.lookup_attendee(badge)
            if 'error' in response:
                session.close()
                return json.dumps(
                    {"success": False, "badge": badge, "reason": "Badge # {} is not found in Uber".format(badge),
                     "vips": get_vip_list()})
            attend = Attendee()
            attend.badge_num = response['result']['badge_num']
            attend.public_id = response['result']['public_id']
            attend.full_name = response['result']['full_name']
            attend.is_vip = True
            session.add(attend)
            session.commit()
            session.close()
            return json.dumps(
                {"success": True, "badge": badge,
                 "reason": "Badge # {} successfully added to VIPs list".format(badge),
                 "vips": get_vip_list()})

        if attend.is_vip:
            session.close()
            return json.dumps({"success": True, "badge": badge,
                               "reason": "Badge # {} already added to VIPs list".format(badge),
                               "vips": get_vip_list()})
        else:
            attend.is_vip = True
            session.commit()
            session.close()
            return json.dumps({"success": True, "badge": badge,
                               "reason": "Badge # {} successfully added to VIPs list".format(badge),
                               "vips": get_vip_list()})

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
                message = 'Meal succesfully added!'
                if not id == '' and not id == 'None':
                    thismeal = session.query(Meal).filter_by(id=id).one()

                    message = 'Meal succesfully updated!'
                else:
                    thismeal = Meal()
            except KeyError:
                thismeal = Meal()

            thismeal.meal_name = params['meal_name']
            thismeal.start_time = utc_tz(params['start_time'])
            thismeal.end_time = utc_tz(params['end_time'])
            thismeal.cutoff = utc_tz(params['cutoff'])
            thismeal.description = params['description']

            thismeal.toggle1_title = params['toggle1_title']
            thismeal.toggle1 = meal_join(session, params, field='toggle1')
            thismeal.toggle2_title = params['toggle2_title']
            thismeal.toggle2 = meal_join(session, params, field='toggle2')
            thismeal.toggle3_title = params['toggle3_title']
            thismeal.toggle3 = meal_join(session, params, field='toggle3')
            thismeal.toggle4_title = params['toggle4_title']
            thismeal.toggle4 = meal_join(session, params, field='toggle4')

            thismeal.toppings1_title = params['toppings1_title']
            thismeal.toppings1 = meal_join(session, params, field='toppings1')
            thismeal.toppings2_title = params['toppings2_title']
            thismeal.toppings2 = meal_join(session, params, field='toppings2')
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
                toggles1 = meal_blank_toppings(meal_split(session, thismeal.toggle1), cfg.radio_select_count)
                toggles2 = meal_blank_toppings(meal_split(session, thismeal.toggle2), cfg.radio_select_count)
                toggles3 = meal_blank_toppings(meal_split(session, thismeal.toggle3), cfg.radio_select_count)
                toggles4 = meal_blank_toppings(meal_split(session, thismeal.toggle4), cfg.radio_select_count)
                if not thismeal.toggle4_title:
                    thismeal.toggle4_title = ""

                toppings1 = meal_blank_toppings(meal_split(session, thismeal.toppings1), cfg.multi_select_count)
                toppings2 = meal_blank_toppings(meal_split(session, thismeal.toppings2), cfg.multi_select_count)
                session.close()
            except sqlalchemy.orm.exc.NoResultFound:
                message = 'Requested Meal ID '+meal_id+' not found'
                session.close()
                raise HTTPRedirect('meal_setup_list?message='+message)

        else:
            # create blank meal
            thismeal = Meal()
            thismeal.meal_name = ''
            thismeal.description = ''
            thismeal.toppings1_title = ''
            thismeal.toppings2_title = ''
            thismeal.toggle1_title = ''
            thismeal.toggle2_title = ''
            thismeal.toggle3_title = ''
            thismeal.toggle4_title = ''
            # make blank boxes for new meal.
            toggles1 = meal_blank_toppings([], cfg.radio_select_count)
            toggles2 = meal_blank_toppings([], cfg.radio_select_count)
            toggles3 = meal_blank_toppings([], cfg.radio_select_count)
            toggles4 = meal_blank_toppings([], cfg.radio_select_count)
            toppings1 = meal_blank_toppings([], cfg.multi_select_count)
            toppings2 = meal_blank_toppings([], cfg.multi_select_count)

        session_info = get_session_info()

        template = env.get_template("meal_edit.html")
        return template.render(meal=thismeal,
                               toggles1=toggles1,
                               toggles2=toggles2,
                               toggles3=toggles3,
                               toggles4=toggles4,
                               toppings1=toppings1,
                               toppings2=toppings2,
                               messages=messages,
                               session=session_info,
                               c=c,
                               cfg=cfg)

    @restricted
    @cherrypy.expose
    def order_edit(self, meal_id='', save_order='', order_id='', message=[], notes='', delete_order=False,
                   dh_edit=False, **params):

        messages = []
        if message:
            text = message
            messages.append(text)

        session_info = get_session_info()

        thisorder = ''
        thismeal = ''

        if delete_order:
            raise HTTPRedirect('order_delete_comfirm?order_id=' + str(delete_order))

        session = models.new_sesh()

        # parameter save_order should only be present if submit clicked
        if save_order:
            # checks if existing order to be updated or new order
            try:
                if dh_edit:
                    attend = session.query(Attendee).filter_by(badge_num=params['badge_number']).one()
                    thisorder = session.query(Order).filter_by(meal_id=save_order,
                                                               attendee_id=attend.public_id).one()
                else:
                    thisorder = session.query(Order).filter_by(meal_id=save_order,
                                                               attendee_id=cherrypy.session['staffer_id']).one()
                # does not update if not belong to user or user is DH/Admin
                thisorder.exists = True  # disables delete button if not set, ie if order does not already exist

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

            now = datetime.utcnow()
            rd = relativedelta(now, thisorder.meal.end_time)

            if rd.minutes > 0 or rd.hours > 0 or rd.days > 0:
                raise HTTPRedirect("staffer_meal_list?message=Pickup orders for this meal time are closed")

            if dh_edit:
                # actually verifies you are admin and not just you edited URL
                # print('starting dh_edit')
                if session_info['is_dh'] or session_info['is_admin']:
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
            thisorder.toggle4 = order_selections(field='toggle4', params=params, is_toggle=True)

            thisorder.toppings1 = order_selections(field='toppings1', params=params)
            thisorder.toppings2 = order_selections(field='toppings2', params=params)
            thisorder.notes = notes

            if dh_edit:  # if the order is being created by the DH Edit method, mark overridden so it will be made.
                thisorder.overridden = True

            if 'dummydata' in params and params['dummydata']:
                shared_functions.dummy_data(params['dummycount'], thisorder)
            else:
                session.add(thisorder)

            session.commit()
            session.close()
            if dh_edit:
                raise HTTPRedirect('dept_order?meal_id=' + str(meal_id) + '&dept_id=' + str(params['department']) +
                                   '&message=Succesfully saved order for badge# ' + str(params['badge_number']))
            else:
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

            sorted_shifts, response = combine_shifts(attend.badge_num, full=True, no_combine=True)
            thisorder.eligible = carryout_eligible(sorted_shifts, response, thismeal.start_time, thismeal.end_time)
            thisorder.exists = True  # disables delete button if not set, ie if order does not already exist
            if thisorder.overridden:
                thisorder.eligible = True

            thismeal.start_time = con_tz(thismeal.start_time)
            thismeal.end_time = con_tz(thismeal.end_time)
            thismeal.cutoff = con_tz(thismeal.cutoff)

            toggles1 = order_split(session, choices=thismeal.toggle1, orders=thisorder.toggle1)
            toggles2 = order_split(session, choices=thismeal.toggle2, orders=thisorder.toggle2)
            toggles3 = order_split(session, choices=thismeal.toggle3, orders=thisorder.toggle3)
            toggles4 = order_split(session, choices=thismeal.toggle4, orders=thisorder.toggle4)

            toppings1 = order_split(session, choices=thismeal.toppings1, orders=thisorder.toppings1)
            toppings2 = order_split(session, choices=thismeal.toppings2, orders=thisorder.toppings2)
            departments = department_split(session, thisorder.department_id)

            template = env.get_template('order_edit.html')
            return template.render(order=thisorder,
                                   meal=thismeal,
                                   attendee=attend,
                                   toggles1=toggles1,
                                   toggles2=toggles2,
                                   toggles3=toggles3,
                                   toggles4=toggles4,
                                   toppings1=toppings1,
                                   toppings2=toppings2,
                                   departments=departments,
                                   messages=messages,
                                   dh_edit=dh_edit,
                                   allergies=allergies,
                                   session=session_info,
                                   c=c,
                                   cfg=cfg)

        if meal_id:
            # print('start meal_id')
            # attempt new order for meal_id
            if dh_edit and (is_dh(cherrypy.session['staffer_id']) or is_admin(cherrypy.session['staffer_id'])):
                # this is when DH or Food Manager is creating an order for another attendee
                try:
                    attend = session.query(Attendee).filter_by(badge_num=params['badge_number']).one()
                    allergies = allergy_info(params['badge_number'])
                except sqlalchemy.orm.exc.NoResultFound:
                    # if attendee not already in DB load from Uber.
                    response = shared_functions.lookup_attendee(params['badge_number'], full=True)

                    if 'error' in response:
                        session.close()
                        raise HTTPRedirect('dept_order?dept_id=' + str(params['department']) + '&meal_id='+str(meal_id)
                                           + '&message=Problem looking up Attendee, '
                                             'please recheck badge number and try again.')

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
                                       '&order_id=' + str(thisorder.id) + '&dept_id=' + str(params['department']) +
                                       '&meal_id=' + str(meal_id) +
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

            thisorder = Order()
            thisorder.attendee_id = cherrypy.session['staffer_id']
            sorted_shifts, response = combine_shifts(attend.badge_num, full=True, no_combine=True)
            thisorder.eligible = carryout_eligible(sorted_shifts, response, thismeal.start_time, thismeal.end_time)
            if thisorder.overridden:
                thisorder.eligible = True

            thismeal.start_time = con_tz(thismeal.start_time)
            thismeal.end_time = con_tz(thismeal.end_time)
            thismeal.cutoff = con_tz(thismeal.cutoff)

            toggles1 = order_split(session, thismeal.toggle1)
            toggles2 = order_split(session, thismeal.toggle2)
            toggles3 = order_split(session, thismeal.toggle3)
            toggles4 = order_split(session, thismeal.toggle4)
            toppings1 = order_split(session, thismeal.toppings1)
            toppings2 = order_split(session, thismeal.toppings2)

            if 'department' in params:
                departments = department_split(session, params['department'])
            else:
                departments = department_split(session)
            thisorder.notes = ''

            template = env.get_template('order_edit.html')
            return template.render(order=thisorder,
                                   meal=thismeal,
                                   attendee=attend,
                                   toggles1=toggles1,
                                   toggles2=toggles2,
                                   toggles3=toggles3,
                                   toggles4=toggles4,
                                   toppings1=toppings1,
                                   toppings2=toppings2,
                                   departments=departments,
                                   messages=message,
                                   dh_edit=dh_edit,
                                   allergies=allergies,
                                   session=session_info,
                                   c=c,
                                   cfg=cfg)

        # if nothing else matched, not creating, loading, saving, or deleting.  therefore, error.
        session.close()
        raise HTTPRedirect('staffer_meal_list?message=You must specify a meal or order ID to create/edit an order.')

    @cherrypy.expose
    @restricted
    def order_delete_confirm(self, order_id='', confirm=False):
        session = models.new_sesh()

        session_info = get_session_info()

        thisorder = session.query(Order).filter_by(id=order_id).one()

        if confirm:
            if thisorder.attendee_id == cherrypy.session['staffer_id'] \
                    or session_info['is_dh'] or session_info['is_admin']:
                session.delete(thisorder)
                session.commit()
                session.close()
                raise HTTPRedirect('staffer_meal_list?message=Order Deleted.')
            else:
                session.close()
                raise HTTPRedirect('staffer_meal_list?message=Order does not belong to you?')

        template = env.get_template('order_delete_confirm.html')
        session.close()
        return template.render(
            order=thisorder,
            session=session_info,
            c=c,
            cfg=cfg)

    @cherrypy.expose
    @admin_req
    def meal_delete_confirm(self, meal_id='', confirm=False):
        # todo: Change system to disable meal instead of physically deleting it so they can be recovered

        session = models.new_sesh()
        session_info = get_session_info()

        thismeal = session.query(Meal).filter_by(id=meal_id).one()

        if confirm:
            redir = 'meal_setup_list?message=Meal ' + thismeal.meal_name + ' has been Deleted.'
            # orders related to the meal must also be deleted to prevent future conflicts if a new meal gets the same ID
            orders = session.query(Order).filter_by(meal_id=meal_id).all()
            dept_orders = session.query(DeptOrder).filter_by(meal_id=meal_id).all()
            session.delete(thismeal)
            if orders:
                for order in orders:
                    session.delete(order)
            if dept_orders:
                for dept_order in dept_orders:
                    session.delete(dept_order)
            session.commit()
            session.close()
            raise HTTPRedirect(redir)

        session.close()

        thismeal.start_time = con_tz(thismeal.start_time)

        template = env.get_template('meal_delete_confirm.html')
        return template.render(
            meal=thismeal,
            session=session_info,
            c=c,
            cfg=cfg)

    @cherrypy.expose
    @restricted
    def staffer_meal_list(self, message=[], display_all=False, **params):
        """
        Display list of meals staffer is eligible for or has already created an order for, unless requested to show all
        """
        # todo: display some information about order status for available meals

        session_info = get_session_info()

        messages = []
        if message:
            text = message
            messages.append(text)

        session = models.new_sesh()

        eligible = ss_eligible(cherrypy.session['badge_num'])

        if not eligible:
            messages.append('You are not scheduled for enough volunteer hours to be eligible for Staff Suite, '
                            'or you have not had your first shift marked as Worked.  '
                            'You will need to get a Department Head to authorize any orders you place.  '
                            'If you work in a non-shift capacity, please click the "Show all meals" button below '
                            'to submit a carryout order.  You will need to have a DH Approve your order '
                            'after it has been created or if your department is a non-shift department you can request '
                            'this change in Slack #Super-Staff-Suite-Ordering-App.')
        try:
            attendee = session.query(Attendee).filter_by(public_id=cherrypy.session['staffer_id']).one()
        except: # todo: be more specific with exceptions
            session.close()

        if 'webhook_url' in params:
            if cherrypy.session['is_dh'] or cherrypy.session['is_admin']:
                # only DH or Admin allowed to use webhook
                if 'webhook_url' in params:
                    # save webhook data
                    attendee.webhook_url = params['webhook_url']
                    attendee.webhook_data = params['webhook_data']
                    session.commit()
                    if attendee.webhook_url and attendee.webhook_data:  # no test if blank webhook
                        shared_functions.send_webhook(params['webhook_url'], params['webhook_data'])
                else:
                    attendee.webhook_url = ''
                    attendee.webhook_data = ''
                # below gets SQLAlchemy to reload attendee from database since needed for page display

        meals = session.query(Meal).order_by(models.meal.Meal.start_time).all()
        sorted_shifts, response = combine_shifts(cherrypy.session['badge_num'], no_combine=True, full=True)

        allergies = allergy_info(cherrypy.session['badge_num'], response)

        meal_display = list()

        session.close()

        now = datetime.utcnow()
        for thismeal in meals:
            try:
                # orders = session.query(Order).filter_by(meal_id=thismeal.id,
                #                                         attendee_id=cherrypy.session['staffer_id']).all()
                # todo: more efficient code for this, I think there's a way to load orders for all meals in one query request
                thisorder = session.query(Order).filter_by(meal_id=thismeal.id,
                                                           attendee_id=cherrypy.session['staffer_id']).one()
                thismeal.order_exists = True
                if thisorder.overridden:
                    thismeal.overridden = True
            except sqlalchemy.orm.exc.NoResultFound:
                pass

        for meal in meals:
            # determining whether user is automatically eligible for a specific meal
            meal.eligible = carryout_eligible(sorted_shifts, response, meal.start_time, meal.end_time)

            # if eligible, or the user has an order AND meal not in past then add to display
            # if display of all was requested then add regardless
            if meal.eligible or display_all or meal.order_exists:
                delta = relativedelta(meal.end_time, now)
                # rd is negative if first item is before second
                rd = 0
                rd += delta.minutes
                rd += delta.hours * 60
                rd += delta.days * 1440
                # hides meals more than 2 hours in the past by default
                if rd >= 120 or display_all or meal.order_exists:
                    # update time to be Con TZ for display purposes
                    meal.start_time = con_tz(meal.start_time)
                    meal.end_time = con_tz(meal.end_time)
                    meal.cutoff = con_tz(meal.cutoff)
                    meal_display.append(meal)

        if len(meal_display) == 0 and eligible:
            messages.append('You are not signed up for any shifts that overlap with meal times. '
                            'If you work in a non-shift capacity, please click the "Show all meals" button below '
                            'to submit a carryout order.  You will need to have a DH Approve your order '
                            'after it has been created or if your department is a non-shift department you can request '
                            'this change in Slack #Super-Staff-Suite-Ordering.')

        template = env.get_template('staffer_meal_list.html')
        return template.render(messages=messages,
                               meallist=meal_display,
                               allergies=allergies,
                               attendee=attendee,
                               session=session_info,
                               c=c,
                               cfg=cfg)

    @cherrypy.expose
    @admin_req
    def config(self, badge='', search='', message=[], delete_order='', full_lookup=False, **params):
        messages = []

        if message:
            text = message
            messages.append(text)

        session_info = get_session_info()

        if delete_order:
            if not session_info['is_super_admin']:
                raise HTTPRedirect('config?message=You must be super admin to delete orders here.')
            session = models.new_sesh()
            thisorder = session.query(Order).filter_by(id=delete_order).one()
            session.delete(thisorder)
            session.commit()
            session.close()
            raise HTTPRedirect('config?message=order ' + delete_order + ' deleted.')

        if 'radio_select_count' in params:
            # save config

            admin_list = params['admin_list']
            staffer_list = params['staffer_list']

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

            if 'early_login_enabled' in params:
                cfg.early_login_enabled = True

            else:
                cfg.early_login_enabled = False

            cfg.room_location = params['room_location']
            cfg.location_url = params['location_url']
            cfg.ss_url = params['ss_url']
            if 'staff_barcode' in params and params['staff_barcode']:
                # adds given barcode or badge number to staff suite staffers list
                shared_functions.add_access(params['staff_barcode'], 'staff')
                staffer_list = ',\n'.join(cfg.staffer_list)
            if 'admin_barcode' in params and params['admin_barcode']:
                # adds given barcode or badge number to admin list
                shared_functions.add_access(params['admin_barcode'], 'admin')
                admin_list = ',\n'.join(cfg.admin_list)
            manager_list = ',\n'.join(cfg.food_managers)

            cfg.save(admin_list, staffer_list, manager_list)

            raise HTTPRedirect('config?message=Successfully saved config settings')

        # load lists into plain string for display in webpage
        admin_list = ',\n'.join(cfg.admin_list)
        staffer_list = ',\n'.join(cfg.staffer_list)

        if badge:
            if not session_info['is_super_admin']:
                raise HTTPRedirect('config?message=You must be super admin to use the attendee lookup feature')
            # lookup attendee in Uber, dumps result to page.  intended for troubleshooting purposes
            attendee = shared_functions.lookup_attendee(badge, full_lookup)
            attendee = json.dumps(attendee, indent=2)
            template = env.get_template('config.html')
            return template.render(messages=messages,
                                   session=session_info,
                                   admin_list=admin_list,
                                   staffer_list=staffer_list,
                                   attendee=attendee,
                                   c=c,
                                   cfg=cfg)

        if search:
            if not session_info['is_super_admin']:
                raise HTTPRedirect('config?message=You must be super admin to use the attendee search feature')
            # lookup attendee in Uber, dumps result to page.  intended for troubleshooting purposes
            attendee = shared_functions.search_attendee(search, full_lookup)
            attendee = json.dumps(attendee, indent=2)
            template = env.get_template('config.html')
            return template.render(messages=messages,
                                   session=session_info,
                                   admin_list=admin_list,
                                   staffer_list=staffer_list,
                                   attendee=attendee,
                                   c=c,
                                   cfg=cfg)

        if "meals_import" in params:
            self.import_meals(params['meals_import'])

        # if no other functions happening, display current settings
        template = env.get_template('config.html')
        return template.render(messages=messages,
                               session=session_info,
                               admin_list=admin_list,
                               staffer_list=staffer_list,
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
            if not cherrypy.session['is_super_admin']:
                raise HTTPRedirect('config?message=You must be super admin to reset the department list.')
            depts = session.query(Department).all()
            for dept in depts:
                session.delete(dept)
            session.commit()
            shared_functions.load_departments()

        if reset_checkin_list:
            if not cherrypy.session['is_super_admin']:
                raise HTTPRedirect('config?message=You must be super admin to reset the checkins log.')
            checkins = session.query(Checkin).all()
            for checkin in checkins:
                session.delete(checkin)
            session.commit()

        session.close()
        raise HTTPRedirect("config")

    @cherrypy.expose
    @dh_or_admin
    def dept_order_selection(self, message='', show_all=False, **params):
        """
        Allows DH or food manager to select meal time and which department they wish to view the dept_order for.
        Filters meal list to only show future meals by default (by end time, not start time)
        Filters selectable departments to only include ones the DH is assigned to unless user is Admin
        """
        messages = []
        if message:
            text = message
            messages.append(text)

        session_info = get_session_info()

        # meal_id would be present if Select button is clicked, sends to selected dept_order
        if 'meal_id' in params:
            raise HTTPRedirect('dept_order?meal_id=' + str(params['meal_id']) + '&dept_id=' + str(params['dept_id']))

        session = models.new_sesh()
        departments = department_split(session)

        meals = session.query(Meal).order_by(Meal.start_time).all()
        meal_list = list()

        for meal in meals:
            rd = relativedelta(now_utc(), meal.end_time)
            if rd.days <= 0 and rd.hours <= 0 and rd.minutes <= 0 or show_all:
                meal.start_time = con_tz(meal.start_time)
                meal.end_time = con_tz(meal.end_time)
                meal.cutoff = con_tz(meal.cutoff)
                meal_list.append(meal)

        session.close()
        template = env.get_template("dept_order_selection.html")
        return template.render(depts=departments,
                               meals=meal_list,
                               session=session_info,
                               messages=messages,
                               c=c,
                               cfg=cfg)

    @cherrypy.expose
    @dh_or_admin
    def dept_order(self, meal_id, dept_id, message="", **params):
        """
        list of orders for selected meal and department for Department Heads and admins
        Can override ones not already eligible
        Can edit existing ones if need be (usually shouldn't)
        Can create new orders for specified badge number
        Will disable all these features once the dept order is started
        """

        messages = []
        if message:
            text = message
            messages.append(text)

        session_info = get_session_info()

        # editing a user's order
        if 'order_badge' in params:
            raise HTTPRedirect('order_edit?dh_edit=True&meal_id=' + str(meal_id) + '&badge_number=' +
                               str(params['order_badge']) + '&department=' + str(params['order_department']))

        # adding food manager.  Food managers access orders for any department
        if 'food_manager' in params:
            success = shared_functions.add_access(params['food_manager'], 'food_manager')
            # adding is succesful if badge # or barcode is found AND not already in list
            if success:
                raise HTTPRedirect('dept_order?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                                   '&message=Food Manager Succesfully Added')
            else:
                session = models.new_sesh()
                attend = session.query(Attendee).filter_by(badge_num=params['food_manager']).one()
                session.close()
                if attend.public_id in cfg.food_managers:
                    raise HTTPRedirect('dept_order?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                                       '&message=Food Manager already added to list')
                else:
                    raise HTTPRedirect('dept_order?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                                       '&message=Error adding food manager.  Invalid badge number?')

        session = models.new_sesh()

        dept = session.query(Department).filter_by(id=dept_id).one()

        # adds note about contact info to top of page if no contact info is filled out
        if not dept.slack_channel and not dept.slack_contact and not dept.other_contact and not dept.sms_contact \
                and not dept.email_contact:
            no_contact = True
        else:
            no_contact = False

        thismeal = session.query(Meal).filter_by(id=meal_id).one()

        # tries to load existing dept order, if none creates a new one.
        try:
            this_dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            this_dept_order = create_dept_order(dept_id, meal_id, session)

            session.commit()
            # reload order since commit flushes it from cache (apparently)
            this_dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()
            thismeal = session.query(Meal).filter_by(id=meal_id).one()
            dept = session.query(Department).filter_by(id=dept_id).one()

        if 'slack_channel' in params or 'sms_contact' in params or 'email_contact' in params or 'other_contact' in params:
            # save changes to dept's contact info
            if 'slack_channel' in params:
                dept.slack_channel = params['slack_channel']
            else:
                dept.slack_channel = ""
            if 'slack_contact' in params:
                dept.slack_contact = params['slack_contact']
            else:
                dept.slack_contact = ""
            if 'email_contact' in params:
                dept.email_contact = params['email_contact']
            else:
                dept.email_contact = ""
            if 'sms_contact' in params:
                dept.sms_contact = params['sms_contact']
            else:
                dept.sms_contact = ""
            if 'other_contact' in params:
                dept.other_contact = params['other_contact']
            else:
                dept.other_contact = ""

            session.commit()
            # reload these items since commit flushes them
            dept = session.query(Department).filter_by(id=dept_id).one()
            thismeal = session.query(Meal).filter_by(id=meal_id).one()
            this_dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()

            messages.append(str(dept.name) + 'Department contact info successfully updated.')

        order_list = session.query(Order).filter_by(meal_id=meal_id, department_id=dept_id).options(
            subqueryload(Order.attendee)).all()

        for order in order_list:
            sorted_shifts, response = combine_shifts(order.attendee.badge_num, no_combine=True, full=True)
            order.eligible = carryout_eligible(sorted_shifts, response, thismeal.start_time, thismeal.end_time)

        if len(order_list) == 0:
            messages.append('Your department does not have any orders for this meal.')

        thismeal.start_time = con_tz(thismeal.start_time)
        thismeal.end_time = con_tz(thismeal.end_time)
        thismeal.cutoff = con_tz(thismeal.cutoff)

        departments = department_split(session, dept_id)

        session.close()

        if this_dept_order.started:
            this_dept_order.start_time = con_tz(this_dept_order.start_time).strftime(cfg.date_format)
        if this_dept_order.completed:
            this_dept_order.completed_time = con_tz(this_dept_order.completed_time).strftime(cfg.date_format)

        template = env.get_template('dept_order.html')
        return template.render(dept=dept,
                               orders=order_list,
                               dept_order=this_dept_order,
                               meal=thismeal,
                               departments=departments,
                               no_contact=no_contact,
                               messages=messages,
                               session=session_info,
                               c=c,
                               cfg=cfg)

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
            message = 'Approval removed for ' + str(order.attendee.badge_num) + ', ' + str(order.attendee.full_name)
        else:
            order.overridden = True
            message = 'Approval added for ' + str(order.attendee.badge_num) + ', ' + str(order.attendee.full_name)
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

        session_info = get_session_info()

        session = models.new_sesh()

        meals = session.query(Meal).order_by(Meal.start_time).all()
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
            if rd.days < 0 and not display_all:
                continue
            if rd.hours < 0 and not display_all:
                continue
            if rd.minutes < 0 and not display_all:
                continue

            # if meal is in future or display_all is True, add to list
            count = session.query(Order).filter_by(meal_id=meal.id).count()
            meal_list.append({'id': meal.id, 'name': meal.meal_name, 'start': con_tz(meal.start_time),
                              'end': con_tz(meal.end_time), 'count': count})

        session.close()
        template = env.get_template('ssf_meal_list.html')
        return template.render(meallist=meal_list,
                               session=session_info,
                               c=c,
                               cfg=cfg)

    @cherrypy.expose
    @ss_staffer
    def ssf_dept_list(self, meal_id, meal_name, **params):
        """
        For chosen meal, shows list of departments with how many orders are currently submitted for that department
        Fulfilment staff can select a department to view order details.
        """

        session_info = get_session_info()

        session = models.new_sesh()

        depts = session.query(models.department.Department).all()
        dept_list = list()
        completed_depts = list()
        orderless_depts = list()
        total_orders = 0
        remaining_orders = 0
        no_remaining_orders = False
        order_fulfilment_completed = False

        for dept in depts:
            # todo: make this count only eligible orders, but will require ~30 seconds to load if done by plain loop
            order_count = session.query(Order).filter_by(department_id=dept.id, meal_id=meal_id).count()

            try:
                dept_order = session.query(DeptOrder).filter_by(dept_id=dept.id, meal_id=meal_id).one()
            except sqlalchemy.orm.exc.NoResultFound:
                # dept_order may not exist yet if no DH or Admin has looked at it
                dept_order = create_dept_order(dept.id, meal_id, session)

            if order_count == 0 and not dept_order.completed:
                orderless_depts.append((dept.name, order_count, dept.id))
                continue

            if dept_order.completed:
                completed_depts.append((dept.name, order_count, dept.id))
            else:
                # if not empty, and not already completed add to primary list
                dept_list.append((dept.name, order_count, dept.id))
                remaining_orders += order_count

            total_orders += order_count

        if 'complete_remaining' in params and params['complete_remaining']:
            # locks all remaining orders for dept and meal then checks if any remaining orders for meal
            # if no remaining orders marks them complete
            for dept in orderless_depts:
                self.ssf_lock_order(meal_id, dept[2], no_redirect=True)
            for dept in orderless_depts:
                order_count = session.query(Order).filter_by(department_id=dept[2], meal_id=meal_id).count()
                if order_count == 0:
                    self.ssf_complete_order(meal_id, dept[2], no_redirect=True)
            session.close()
            raise HTTPRedirect('ssf_dept_list?meal_id=' + str(meal_id) + '&meal_name=' + meal_name)

        if remaining_orders == 0:
            no_remaining_orders = True

        if len(dept_list) == 0 and len(orderless_depts) == 0:
            order_fulfilment_completed = True

        # todo: if remaining orders 0 then offer button to lock and then complete empty depts
        # todo: needs to lock, then check orderless list again if 0 remaining before marking all complete
        # todo: probably sleep 1 between locking and checking for orders to make sure any in-progress commits finish

        session.close()
        template = env.get_template('ssf_dept_list.html')
        return template.render(depts=dept_list,
                               meal_id=meal_id,
                               meal_name=meal_name,
                               total=total_orders,
                               remaining=remaining_orders,
                               completed_depts=completed_depts,
                               orderless_depts=orderless_depts,
                               no_remaining_orders=no_remaining_orders,
                               order_fulfilment_completed=order_fulfilment_completed,
                               session=session_info,
                               c=c,
                               cfg=cfg)

    @cherrypy.expose
    @ss_staffer
    def ssf_orders(self, meal_id, dept_id, message=[]):
        """
        Shows list of orders for selected meal and department.
        Has buttons to lock order for fulfilment, or if already locked by mistake to unlock.
        Once order is locked buttons to print all orders or individual orders become available
        Button to mark department order complete - notifies departments it's ready for pickup
        """

        session_info = get_session_info()

        rendered_template = None

        messages = []
        if message:
            text = message
            messages.append(text)

        session = models.new_sesh()
        try:
            dept_order = session.query(DeptOrder).filter_by(dept_id=dept_id, meal_id=meal_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            # dept_order may not exist yet if no DH or Admin has looked at it
            dept_order = create_dept_order(dept_id, meal_id, session)

        orders = session.query(Order).filter_by(department_id=dept_id, meal_id=meal_id) \
            .options(joinedload(Order.attendee)).all()

        thismeal = session.query(Meal).filter_by(id=meal_id).one()

        dept = session.query(Department).filter_by(id=dept_id).one()
        dept_name = dept.name

        session.close()  # this has to be before the order loop below or you get errors

        order_list = list()
        for order in orders:
            sorted_shifts, response = combine_shifts(order.attendee.badge_num, full=True, no_combine=True)
            try:
                order.eligible = carryout_eligible(sorted_shifts, response, thismeal.start_time, thismeal.end_time)
                # if not eligible and not overridden, remove from list for display/printing
                # todo: maybe add notification that one or more orders placed are not eligible and therefore not in list?
            except KeyError:
                order.eligible = True
                # someone's order is crashing because it doesn't get a response.
                # going to err on the side of giving them food if possible.

            order.toggle1 = return_selected_only(session, choices=thismeal.toggle1, orders=order.toggle1)
            order.toggle2 = return_selected_only(session, choices=thismeal.toggle2, orders=order.toggle2)
            order.toggle3 = return_selected_only(session, choices=thismeal.toggle3, orders=order.toggle3)
            order.toggle4 = return_selected_only(session, choices=thismeal.toggle4, orders=order.toggle4)

            order.toppings1 = return_selected_only(session, choices=thismeal.toppings1, orders=order.toppings1)
            order.toppings2 = return_selected_only(session, choices=thismeal.toppings2, orders=order.toppings2)

            # below modifications allows fulfilment to limp along if major meal changes are needed.
            if len(order.toggle1) == 0:
                thismeal.toggle1_title = ''
            if len(order.toggle2) == 0:
                thismeal.toggle2_title = ''
            if len(order.toggle3) == 0:
                thismeal.toggle3_title = ''
            if len(order.toggle4) == 0:
                thismeal.toggle4_title = ''

            if len(order.toppings1) == 0:
                thismeal.toppings1_title = ''
            if len(order.toppings2) == 0:
                thismeal.toppings2_title = ''

            try:
                if response['result']['food_restrictions']:
                    if response['result']['food_restrictions']['standard_labels'] or \
                            response['result']['food_restrictions']['freeform']:
                        order.allergies = {'standard_labels': response['result']['food_restrictions']['standard_labels'],
                                           'freeform': response['result']['food_restrictions']['freeform']}
            except KeyError:
                pass

            if order.eligible or order.overridden:
                order_list.append(order)

        if dept_order.started:
            # fix time zone for display
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

                # remove invalid filename characters for when the PDF creator saves the file
                replacement_list = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
                for char in replacement_list:
                    dept_name = dept_name.replace(char, '-')

                # render page before changing list page uses to render
                template = env.get_template('ssf_orders.html')
                rendered_template = template.render(dept_order=dept_order,
                                dept_name=dept_name,
                                dept_id=dept_id,
                                order_list=order_list,
                                meal=thismeal,
                                messages=messages,
                                session=session_info,
                                c=c,
                                cfg=cfg)

                for order in order_list:
                    try:
                        allergies_freeform = order.allergies['freeform']
                    except TypeError:
                        allergies_freeform = ""
                    if (len(order.notes) > 80) and (len(allergies_freeform) > 80):
                        order.notes = "<<< Notes too long for printing, please look at order fulfilment page to read >>>"
                        order.allergies['freeform'] = "<<< Allergies too long for printing, please look at order fulfilment page to read >>>"
                    if len(order.notes) > 140:
                        order.notes = "<<< Notes too long for printing, please look at order fulfilment page to read >>>"
                    if len(allergies_freeform) > 140:
                        order.allergies['freeform'] = "<<< Allergies too long for printing, please look at order fulfilment page to read >>>"

                if cfg.env == "dev":  # Windows todo: change this to detect OS instead
                    # for some reason the silly system decided to not find wkhtmltopdf automatically anymore on Windows
                    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
                    config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

                    rendered_labels = labels.render(orders=order_list,
                                                    meal=thismeal,
                                                    dept_name=dept_name,
                                                    date=thismeal.start_time.strftime("%d-%m-%Y"))

                    pdfkit.from_string(rendered_labels,
                                       'pdfs\\' + dept_name + '.pdf',
                                       options=options,
                                       configuration=config)
                else:   # Linux seems to find the package automatically
                    # path_wkhtmltopdf = r'/usr/local/bin/wkhtmltopdf'
                    # config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
                    pdfkit.from_string(labels.render(orders=order_list,
                                                     meal=thismeal,
                                                     dept_name=dept_name,
                                                     date=thismeal.start_time.strftime("%d-%m-%Y")),
                                       'pdfs/' + dept_name + '.pdf',
                                       options=options)
        if dept_order.completed:
            dept_order.completed_time = con_tz(dept_order.completed_time).strftime(cfg.date_format)

        if not rendered_template:
            template = env.get_template('ssf_orders.html')
            rendered_template = template.render(dept_order=dept_order,
                                                dept_name=dept_name,
                                                dept_id=dept_id,
                                                order_list=order_list,
                                                meal=thismeal,
                                                messages=messages,
                                                session=session_info,
                                                c=c,
                                                cfg=cfg)

        return rendered_template

    @cherrypy.expose
    @ss_staffer
    def ssf_lock_order(self, meal_id, dept_id, unlock_order=False, no_redirect=False):
        """
        Locks or unlocks dept_order and individual orders for selected meal and department
        """
        session = models.new_sesh()
        dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()
        orders = session.query(Order).filter_by(meal_id=meal_id, department_id=dept_id).all()

        if unlock_order:
            if dept_order.completed:
                session.close()
                if no_redirect:
                    return
                raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                                   '&message=You cannot un-lock an order Bundle that is marked Completed.')

            dept_order.started = False
            dept_order.start_time = None
            for order in orders:
                order.locked = False
            session.commit()
            session.close()
            if no_redirect:
                return
            raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                               '&message=This order Bundle is now un-locked.')

        dept_order.started = True
        dept_order.start_time = now_utc()
        for order in orders:
            order.locked = True
        session.commit()
        session.close()
        if no_redirect:
            return
        raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                           '&message=This order Bundle is now locked.')


    @cherrypy.expose
    @ss_staffer
    def ssf_complete_order(self, meal_id, dept_id, uncomplete_order=False, no_redirect=False):
        """
        Marks or unmarks department order as complete for selected meal and department
        """
        session = models.new_sesh()
        dept_order = session.query(DeptOrder).filter_by(meal_id=meal_id, dept_id=dept_id).one()

        if uncomplete_order:
            dept_order.completed = False
            dept_order.completed_time = None
            session.commit()
            session.close()
            if no_redirect:
                return
            raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                               '&message=This Bundle is now un-marked Complete.')

        if not dept_order.started:
            session.close()
            if no_redirect:
                return
            raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                               '&message=The Bundle must be Locked before it can be marked Complete.')

        dept_order.completed = True
        dept_order.completed_time = now_utc()

        orders = session.query(models.order.Order).filter_by(meal_id=meal_id, department_id=dept_id).all()
        # if no orders for department, skip notifying them.
        if len(orders) == 0:
            session.commit()
            session.close()
            if no_redirect:
                return
            raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                               '&message=This Bundle is now marked Complete.')
        shared_functions.send_completion_messages(dept_id, meal_id)

        if dept_order.other_contact:
            session.commit()
            session.close()
            if no_redirect:
                return
            raise HTTPRedirect('dept_order_details?dept_order_id=' + str(dept_order.id) +
                               '&message=This department has requested manual contact.  '
                               'Please contact them as listed in the Other Contact Info box.  '
                               'This Bundle is now marked Complete.')
        session.commit()
        session.close()
        if no_redirect:
            return
        raise HTTPRedirect('ssf_orders?meal_id=' + str(meal_id) + '&dept_id=' + str(dept_id) +
                           '&message=This Bundle is now marked Complete.')

    @dh_or_staffer
    @cherrypy.expose
    def dept_order_details(self, dept_order_id, **params):
        """
        Displays contact info details for a dept's order
        Intended for use by fulfilment team
        :param dept_order_id:
        :return:
        """
        # todo: fix this page to do smart load / save of contact details
        session_info = get_session_info()

        session = models.new_sesh()
        print('------------dept_order_id ' + dept_order_id + ' -------------')
        dept_order = session.query(DeptOrder).filter_by(id=dept_order_id).one()

        if 'slack_channel' in params or 'slack_contact' in params or 'sms_contact' in params or \
                'email_contact' in params or 'other_contact' in params:
            # save record
            dept_order.slack_contact = params['slack_contact']
            dept_order.slack_channel = params['slack_channel']
            dept_order.sms_contact = params['sms_contact']
            dept_order.email_contact = params['email_contact']
            # dept_order.other_contact = params['other_contact']
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
                               c=c,
                               cfg=cfg)

    @dh_or_staffer
    @cherrypy.expose
    def dept_contact(self, dept_id="", message="", original_location=None, send_test=False, **params):
        """
        Displays and allows updating of Department's default contact info
        """
        print("")
        messages = []
        if message:
            text = message
            messages.append(text)

        session_info = get_session_info()

        original_location = shared_functions.create_valid_user_supplied_redirect_url(original_location,
                                                                                     default_url='staffer_meal_list')

        session = models.new_sesh()

        if dept_id:
            # Submitting main form
            dept = session.query(Department).filter_by(id=dept_id).one()
            dept_id_dropdown = dept_id
            departments = department_split(session, dept_id_dropdown)
        elif "dept_id_dropdown" in params:
            # Choosing department from dropdown
            dept = session.query(Department).filter_by(id=params['dept_id_dropdown']).one()
            dept_id_dropdown = params['dept_id_dropdown']
            departments = department_split(session, dept_id_dropdown)
        else:
            # When going to page without having already chosen a dept
            dept = ""
            dept_id_dropdown = ""
            departments = department_split(session)

        if 'slack_channel' in params:
            # save record
            dept.slack_contact = params['slack_contact']
            dept.slack_channel = params['slack_channel']
            dept.sms_contact = params['sms_contact']
            dept.email_contact = params['email_contact']
            # dept.other_contact = params['other_contact']
            session.commit()
            dept = session.query(Department).filter_by(id=dept_id).one()

        if send_test:
            errors = shared_functions.send_completion_messages(dept_id, session=session)
            if errors:
                messages.append("One or more of your contact methods produced an error: " + errors)

        session.close()

        template = env.get_template('dept_contact.html')
        return template.render(dept=dept,
                               dept_id_dropdown=dept_id_dropdown,
                               depts=departments,
                               original_location=original_location,
                               messages=messages,
                               session=session_info,
                               c=c,
                               cfg=cfg)

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
            checkin.timestamp = con_tz(checkin.timestamp)
            export += checkin.timestamp.strftime(cfg.date_format)
            export += '\n'

        exportfile = open('pdfs/checkin_export.csv', 'w')
        exportfile.write(export)
        exportfile.close()

        session.close()
        raise HTTPRedirect('pdfs/checkin_export.csv')

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
            shifts, response = combine_shifts(order.attendee.badge_num, no_combine=True, full=True)
            if "error" in response:
                export += 'Error'
            else:
                export += str(shared_functions.carryout_eligible(shifts, response, order.meal.start_time, order.meal.end_time))
            export += ','
            replacement_list = [',', ';', '\r', '\n', '\t']
            for char in replacement_list:
                order.notes = order.notes.replace(char, ' - ')
            export += order.notes
            export += '\n'

        end = datetime.utcnow()
        rd = relativedelta(start, end)
        print('-------------done generating orders CSV--------------')
        print(str(rd.minutes) + ' minutes, ' + str(rd.seconds) + ' seconds')

        exportfile = open('pdfs/order_export.csv', 'w', encoding='utf-8')
        exportfile.write(export)
        exportfile.close()

        session.close()
        raise HTTPRedirect('pdfs/order_export.csv')

    @cherrypy.expose
    @admin_req
    def export_meals(self):
        """
        Creates a JSON file with meals list, that can be imported into a server instance
        """
        session = models.new_sesh()
        export = {}
        meals = session.query(models.meal.Meal).all()
        toppings = session.query(models.ingredient.Ingredient).all()

        export['meals'] = list()
        for index, meal in enumerate(meals):
            export['meals'].append({})
            # export['meals'][index] = {}
            export['meals'][index]['meal_name'] = meal.meal_name
            export['meals'][index]['start_time'] = meal.start_time.strftime(cfg.date_format)
            export['meals'][index]['end_time'] = meal.end_time.strftime(cfg.date_format)
            export['meals'][index]['cutoff'] = meal.cutoff.strftime(cfg.date_format)
            export['meals'][index]['locked'] = meal.locked
            export['meals'][index]['description'] = meal.description
            export['meals'][index]['detail_link'] = meal.detail_link

            export['meals'][index]['toggle1'] = meal.toggle1
            export['meals'][index]['toggle1_title'] = meal.toggle1_title
            export['meals'][index]['toggle2'] = meal.toggle2
            export['meals'][index]['toggle2_title'] = meal.toggle2_title
            export['meals'][index]['toggle3'] = meal.toggle3
            export['meals'][index]['toggle3_title'] = meal.toggle3_title
            export['meals'][index]['toggle4'] = meal.toggle4
            export['meals'][index]['toggle4_title'] = meal.toggle4_title

            export['meals'][index]['toppings1'] = meal.toppings1
            export['meals'][index]['toppings1_title'] = meal.toppings1_title
            export['meals'][index]['toppings2'] = meal.toppings2
            export['meals'][index]['toppings2_title'] = meal.toppings2_title

        export['ingredients'] = list()
        for index, topping in enumerate(toppings):
            export['ingredients'].append({})
            # export['ingredients'][index] = {}
            export['ingredients'][index]['id'] = topping.id
            export['ingredients'][index]['label'] = topping.label
            export['ingredients'][index]['description'] = topping.description
            export['ingredients'][index]['sort_by'] = topping.sort_by

        session.close()
        fileexport = open("pdfs/meal_export.json", 'w')
        json.dump(export, fileexport, indent=2)
        fileexport.close()
        raise HTTPRedirect('pdfs/meal_export.json')

    @admin_req
    def import_meals(self, jsondata):
        """
        Loads meals in from JSON list
        ERASES ALL EXISTING MEALS AND ORDERS
        """
        session = models.new_sesh()
        dept_orders = session.query(models.dept_order.DeptOrder).delete()
        orders = session.query(models.order.Order).delete()
        toppings = session.query(models.ingredient.Ingredient).delete()
        meals = session.query(models.meal.Meal).delete()

        print("deleted " + str(meals) + " meals from database")
        print("deleted " + str(toppings) + " ingredients from database")
        print("deleted " + str(orders) + " orders from database")
        try:
            importdata = json.loads(jsondata)
        except json.decoder.JSONDecodeError:
            raise HTTPRedirect("config?message=Invalid JSON format")

        for index, export in enumerate(importdata['meals']):
            meal = Meal()
            meal.meal_name = export['meal_name']
            meal.start_time = shared_functions.parse_utc(export['start_time'])
            meal.end_time = shared_functions.parse_utc(export['end_time'])
            meal.cutoff = shared_functions.parse_utc(export['cutoff'])
            meal.locked = export['locked']
            meal.description = export['description']
            meal.detail_link = export['detail_link']

            meal.toggle1 = export['toggle1']
            meal.toggle1_title = export['toggle1_title']
            meal.toggle2 = export['toggle2']
            meal.toggle2_title = export['toggle2_title']
            meal.toggle3 = export['toggle3']
            meal.toggle3_title = export['toggle3_title']
            meal.toggle4 = export['toggle4']
            meal.toggle4_title = export['toggle4_title']

            meal.toppings1 = export['toppings1']
            meal.toppings1_title = export['toppings1_title']
            meal.toppings2 = export['toppings2']
            meal.toppings2_title = export['toppings2_title']
            session.add(meal)

        for index, export in enumerate(importdata['ingredients']):
            topping = models.ingredient.Ingredient()
            topping.id = export['id']
            topping.label = export['label']
            topping.description = export['description']
            topping.sort_by = export['sort_by']
            session.add(topping)

        session.commit()
        session.close()
        return json.dumps(export, indent=2)

    @cherrypy.expose
    @admin_req
    def export_completion_csv(self):
        """
        Exports to a CSV the dept order list with meal start time, started time, completed time
        """
        session = models.new_sesh()

        orders = session.query(models.dept_order.DeptOrder) \
            .order_by(models.dept_order.DeptOrder.meal_id, models.dept_order.DeptOrder.dept_id) \
            .all()
        export = "Meal,Department,Meal Start Time,Time Order Started,Time Order Completed" \
                 ",Difference between Meal Start and Completion\n"
        for order in orders:
            meal = session.query(models.meal.Meal).filter_by(id=order.meal_id).one()
            dept = session.query(models.department.Department).filter_by(id=order.dept_id).one()
            export += meal.meal_name
            export += ','
            export += dept.name
            export += ','
            export += con_tz(meal.start_time).strftime(cfg.date_format)
            export += ','
            if order.start_time:
                export += con_tz(order.start_time).strftime(cfg.date_format)
            export += ','
            if order.completed_time:
                export += con_tz(order.completed_time).strftime(cfg.date_format)
            export += ','
            delta = relativedelta(meal.start_time, order.completed_time)
            export += str(delta.hours) + ' hours ' + str(delta.minutes) + ' minutes'
            export += '\n'

        exportfile = open('pdfs/order_completion_export.csv', 'w', encoding='utf-8')
        exportfile.write(export)
        exportfile.close()

        session.close()
        raise HTTPRedirect('pdfs/order_completion_export.csv')

    @cherrypy.expose
    @ss_staffer
    def custom_label(self, title="", title_size=32, detail_text="", detail_size=14):
        """
        Page for printing custom labels such as to label food or whatever else you want to label.
        """
        if cfg.local_print and (title or detail_text):
            labels = env.get_template('print_custom_label.html')
            options = {
                'page-height': '2.0in',
                'page-width': '4.0in',
                'margin-top': '0.0in',
                'margin-right': '0.0in',
                'margin-bottom': '0.0in',
                'margin-left': '0.0in',
                # 'encoding': "UTF-8",
                # 'print-media-type': None,
                'dpi': '203'
            }
            if cfg.env == "dev":  # Windows todo: change this to detect OS instead
                # for some reason the silly system decided to not find wkhtmltopdf automatically anymore on Windows
                path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
                config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

                rendered_labels = labels.render(title=title,
                                                title_size=title_size,
                                                detail_text=detail_text,
                                                detail_size=detail_size)

                pdfkit.from_string(rendered_labels,
                                   'pdfs\\custom_label.pdf',
                                   options=options,
                                   configuration=config)

            else:  # Linux seems to find the package automatically
                # path_wkhtmltopdf = r'/usr/local/bin/wkhtmltopdf'
                # config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
                pdfkit.from_string(labels.render(title=title,
                                                 title_size=title_size,
                                                 detail_text=detail_text,
                                                 detail_size=detail_size),
                                   'pdfs/custom_label.pdf',
                                   options=options)


        template = env.get_template('custom_label.html')
        return template.render(title=title,
                               title_size=title_size,
                               detail_text=detail_text,
                               detail_size=detail_size,
                               session=get_session_info(),
                               c=c,
                               cfg=cfg)


    @cherrypy.expose
    @admin_req
    def import_export(self):
        """
        Page for importing or exporting DB stuf
        """

        template = env.get_template('import_export.html')
        return template.render(session=get_session_info(),
                               c=c,
                               cfg=cfg,)

    @cherrypy.expose
    @admin_req
    def process_export(self, choice=""):
        """
        Handles top level of exports
        """
        export = {
            "version": cfg.version,
            "export_date": datetime.now().strftime(cfg.date_format)
        }
        cherrypy.response.headers['content-type'] = 'text/json'

        if choice == "meals":
            cherrypy.response.headers['content-disposition'] = 'attachment; filename=meals_export.json'
            export["meals"] = shared_functions.export_meals()

        if choice == "all":
            cherrypy.response.headers['content-disposition'] = 'attachment; filename=everything_export.json'
            export["attendees"] = shared_functions.export_attendees()
            export["checkins"] = shared_functions.export_checkins()
            export["dept_orders"] = shared_functions.export_dept_orders()
            export["ingredients"] = shared_functions.export_ingredients()
            export["meals"] = shared_functions.export_meals()
            export["orders"] = shared_functions.export_orders()

        return json.dumps(export, indent=2)

    @cherrypy.expose
    @admin_req
    def process_import(self, jsondata, **params):
        """
        Handles top level of imports
        """
        if params['meals']:
            shared_functions.import_meals(jsondata['meals'], replace_all=params['replace_meals_list'])

        return


    @cherrypy.expose
    @admin_req
    def export_contact_completion(self):
        """
        Exports CSV of contact info completion, so we can harrass departments who haven't done it yet.
        """
        session = models.new_sesh()
        depts = session.query(models.department.Department).order_by(models.department.Department.name).all()

        export = "Name,has_some_contact_info,is_Shiftless,SMS,Slack_Channel,Slack_Contact,Other\n"
        for dept in depts:
            export += dept.name
            export += ","
            if(dept.sms_contact or dept.slack_channel or dept.other_contact):
                export += "True"
            else:
                export += "False"
            export += ','
            export += re.sub(r'[\r\n;,]', ' ', str(dept.is_shiftless))
            export += ','
            export += re.sub(r'[\r\n;,]', ' ', str(dept.sms_contact))
            export += ','
            export += re.sub(r'[\r\n;,]', ' ', str(dept.slack_channel))
            export += ','
            export += re.sub(r'[\r\n;,]', ' ', str(dept.slack_contact))
            export += ','
            export += re.sub(r'[\r\n;,]', ' ', str(dept.other_contact))
            export += '\n'

        exportfile = open('pdfs/contact_completion_export.csv', 'w', encoding='utf-8')
        exportfile.write(export)
        exportfile.close()

        session.close()
        raise HTTPRedirect('pdfs/contact_completion_export.csv')


    @cherrypy.expose
    @admin_req
    def slack_userlist_reset(self):
        """
        Clears internal Slack user list and reloads full list from Slack server
        """
        session = models.new_sesh()
        data = slack_bot.load_userlist_page()
        users = data["members"]
        # Clear existing users list
        session.query(Slack_User).delete()
        users_to_load = True
        while users_to_load:
            for user in users:
                if user["deleted"]:
                    # do not import deleted users
                    continue

                new_user = Slack_User()
                new_user.id = user["id"]
                new_user.name = user["name"]
                new_user.display_name = user["profile"]["display_name"]
                new_user.real_name = user["profile"]["real_name"]
                session.add(new_user)

            if not data["response_metadata"]["next_cursor"] or data["response_metadata"]["next_cursor"] == "":
                break

            data = slack_bot.load_userlist_page(data["response_metadata"]["next_cursor"])
            users = data["members"]

        data = slack_bot.load_group_list()
        groups = data["usergroups"]
        for user in groups:
            # it says user instead of group so I can just copy the code from above
            new_user = Slack_User()
            new_user.id = user["id"]
            new_user.name = user["handle"]
            new_user.display_name = user["name"]
            new_user.real_name = ""
            session.add(new_user)

        session.commit()
        session.close()

        raise HTTPRedirect('config')
