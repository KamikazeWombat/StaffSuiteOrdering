import requests


from config import cfg


def send_message(channel, message):
    channel_list = channel.split(',')
    for chan in channel_list:
        chan.strip()
        data = {'token': cfg.slack_authkey,
                'link_names': 'true',
                'channel': chan,
                'text': message}
        headers = {'Content-type': 'application/json'}
        response = requests.post('https://slack.com/api/chat.postMessage', data, headers)
