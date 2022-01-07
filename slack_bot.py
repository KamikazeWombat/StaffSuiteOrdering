import json
import requests

from config import cfg


def send_message(channel, message):
    """sends given message to all given channels / users"""

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
                if not json.loads(response.text)['ok']:
                    send_message("@Wombat3", "Error sending Slack message to " + chan + ' - \r\n' + response.text + ' @wombat3')

            data = {'token': cfg.slack_authkey,
                    'link_names': 'true',
                    'unfurl_links': 'false',
                    'channel': chan,
                    'text': message}

            response = requests.post('https://slack.com/api/chat.postMessage', data, headers)

            if not json.loads(response.text)['ok']:
                send_message("#bottesting", "Error sending Slack message to " + chan + ' - \r\n' + response.text + ' @wombat3')

        except Exception:
            send_message("#bottesting", "General Error sending Slack message to " + chan + ' @wombat3')

    return
