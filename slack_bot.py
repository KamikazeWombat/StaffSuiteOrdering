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
