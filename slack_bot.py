import json
import re
import requests

from config import cfg


def send_message(channels, message, is_error_message=False):
    """
    sends given message to all given channels / users
    is_error_message is there because otherwise an error sending an error message creates a loop
    """

    if not cfg.slack_authkey:
        print("----------Slack API key missing so message not sent.----------")
        return
    channels = re.sub(r'[\r\n; ]', ',', channels)
    channel_list = channels.split(',')

    headers = {'Content-type': 'application/json'}

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
                send_message("#bottesting", "Error sending Slack message to " + chan + ' - \r\n' + response.text,
                             is_error_message=True)

        except Exception as e:
            if not is_error_message:
                send_message("@wombat3", "General Error sending Slack message to " + chan + '\r\n' +
                             str(e), is_error_message=True)

    return


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
