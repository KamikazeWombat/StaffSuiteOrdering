import json
import re
import requests

import sqlalchemy.orm.exc
from sqlalchemy import or_

import models
from models.slack_user import Slack_User
from config import cfg


def send_message(channels, message, pings="", is_error_message=False):
    """
    sends given message to all given channels / users
    is_error_message is there because otherwise an error sending an error message creates a loop|
    returns string showing any errors that came up
    """

    if not cfg.slack_authkey:
        print("----------Slack API key missing so message not sent.----------")
        return
    channels = re.sub(r'[\r\n;]', ',', channels)
    channel_list = channels.split(',')

    headers = {'Content-type': 'application/json'}

    pings = re.sub(r'[\r\n;]', ',', pings)
    pings = pings.split(',')
    ping_final = ""
    session = models.new_sesh()
    errors = ""

    for user in pings:
        # look up people in user DB and convert to userids

        user_no_at = re.sub(r'[@]', '', user)
        user_no_at = user_no_at.strip()
        if not user_no_at:
            continue
        try:
            record = session.query(Slack_User).filter(or_(
                Slack_User.name.ilike(f'%{user_no_at}%'),
                Slack_User.display_name.ilike(f'%{user_no_at}%'),
                Slack_User.real_name.ilike(f'%{user_no_at}%')
            )).one()

            ping_final = ping_final + '@' + record.name + " "

        except sqlalchemy.exc.MultipleResultsFound:
            # go ahead and append whatever failed lookup too in case someone included extra info in their message
            record_list = session.query(Slack_User).filter(or_(
                Slack_User.name.ilike(f'%{user_no_at}%'),
                Slack_User.display_name.ilike(f'%{user_no_at}%'),
                Slack_User.real_name.ilike(f'%{user_no_at}%')
            )).all()
            matches_found = 0
            exact_matches = list()
            for record in record_list:
                if (record.name.lower() == user_no_at.lower() or
                        record.display_name.lower() == user_no_at.lower() or
                        record.real_name.lower() == user_no_at.lower()):
                    # in the case of multiple matches checks to see if one is the actual username and includes it if so.
                    exact_matches.append('@' + record.name + " ")
                    matches_found += 1
            if matches_found > 1:
                ping_final = ping_final + user
            if matches_found == 0:
                ping_final = ping_final + user
            if matches_found == 1:
                ping_final = ping_final + exact_matches[0]

        except sqlalchemy.orm.exc.NoResultFound:
            # if nothing matched also go ahead and attach whatever failed lookup in case it's just extra info
            ping_final = ping_final + user

    message = message + ping_final

    for chan in channel_list:
        chan.strip()
        if not chan:
            # if chan blank after removing junk characters then skip
            continue
        try:
            if chan[0] == '@':
                open_channel = {'token': cfg.slack_authkey,
                                'users': chan}
                response = requests.post('https://slack.com/api/conversations.open', open_channel, headers)

            data = {'token': cfg.slack_authkey,
                    'link_names': 'true',
                    'unfurl_links': 'false',
                    'channel': chan,
                    'text': message}

            response = requests.post('https://slack.com/api/chat.postMessage', data, headers)

            if not json.loads(response.text)['ok'] and not is_error_message:
                error = "Error sending Slack message to " + chan + ' - \r\n' + response.text
                send_message("#bottesting", error, is_error_message=True)
                errors = errors + error + "\r\n"

        except Exception as e:
            if not is_error_message:
                error = "General Error sending Slack message to " + chan + '\r\n' + str(e)
                send_message("@wombat3", error, is_error_message=True)
                errors = errors + error + "\r\n"

    return errors


def load_userlist_page(cursor=""):
    """
    Loads page of users.list with optional cursor
    """
    if not cfg.slack_authkey:
        print("----------Slack API key missing so user list request not sent.----------")
        return

    # according to official docs Slack API returns cursor with an '=' at the end which has to be replaced with '%3D'
    # testing shows it returns an error if I actually do the replacement they say is required?  lol
    # cursor = re.sub(r'=', '%3D', cursor)

    headers = {'Content-type': 'application/json'}
    data = {'token': cfg.slack_authkey,
            'limit': 100}
    if cursor:
        data["cursor"] = cursor
        print("--------------cursor: " + cursor + " ------------")

    try:
        response = requests.post('https://slack.com/api/users.list', data, headers)

    except Exception as e:
        send_message("@wombat3", "General Error loading Slack user list" + '\r\n' +
                     str(e), is_error_message=True)

    if json.loads(response.text)['ok']:
        return json.loads(response.text)
    else:
        send_message("#bottesting", "Error loading Slack user list" + ' - \r\n' + response.text,
                     is_error_message=True)
    return


def load_group_list():
    """
    Loads list 0f groups - this seems to return all rather than just a page.
    """
    if not cfg.slack_authkey:
        print("----------Slack API key missing so group list request not sent.----------")
        return

    headers = {'Content-type': 'application/json'}
    data = {'token': cfg.slack_authkey}

    try:
        response = requests.post('https://slack.com/api/usergroups.list', data, headers)

    except Exception as e:
        send_message("@wombat3", "General Error loading Slack group list" + '\r\n' +
                     str(e), is_error_message=True)

    if json.loads(response.text)['ok']:
        return json.loads(response.text)
    else:
        send_message("#bottesting", "Error loading Slack group list" + ' - \r\n' + response.text,
                     is_error_message=True)
    return
