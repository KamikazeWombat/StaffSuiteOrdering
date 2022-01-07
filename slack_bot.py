import json
import requests

from config import cfg


def send_message(channel, message, is_error_message=False):
    """
    sends given message to all given channels / users
    is_error_message is there because otherwise an error sending an error message creates a loop
    """

    if not cfg.slack_authkey:
        print("----------Slack API key missing so message not sent.----------")
        return

    headers = {'Content-type': 'application/json'}

    channel_list = channel.split(',')
    for chan in channel_list:
        try:
            if chan and chan[0] == '@':
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

        except Exception:
            if not is_error_message:
                send_message("@wombat3", "General Error sending Slack message to " + chan, is_error_message=True)

    return
