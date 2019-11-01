import requests


from config import cfg


def send_message(channel, message):
    data = {'token': cfg.slack_authkey,
            'link_names': 'true',
            'channel': channel,
            'text': message}
    headers = {'Content-type': 'application/json'}
    response = requests.post('https://slack.com/api/chat.postMessage', data, headers)
