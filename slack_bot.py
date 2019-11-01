import requests


from config import cfg


def send_message(channel, message):
    print('-------------slackbot.send_message----------------')
    data = {'token': cfg.slack_authkey,
            'link_names': 'true',
            'channel': channel,
            'text': message}
    headers = {'Content-type': 'application/json'}
    response = requests.post('https://slack.com/api/chat.postMessage', data, headers)
    print(response.text)
    """
    list_req = {'token': 'xoxp-2702698520-122262234839-819371652551-cb94d70eb4aadadad99b6b29595fc34c',
                'exclude_members': 'true',
                'exclude_archived': 'true'}
    headers2 = {'Content-type': 'application/x-www-form-urlencoded'}
    response2 = requests.post('https://slack.com/api/channels.list', list_req, headers2)
    print('----------------------------------------')
    print(response2.text)"""