import time
import re

from twilio.rest import Client

import slack_bot
from config import cfg


def send_message(phone_numbers, dept_name, meal_name):
    """
    Sends message to list of phone numbers
    """
    client = Client(cfg.twilio_sid, cfg.twilio_authkey)

    for index, phone in enumerate(phone_numbers):
        if index % 5 == 0:
            time.sleep(5)
        # remove hyphens and such from phone number
        phone = re.sub(r'[-,()\.\+a-zA-Z]', '', phone)

        # if nor 1 for country code at beginning of number
        # I think this should ignore if someone has given an international number, at least in most cases.
        if phone.len() == 10:
            phone = '1' + phone

        # Twilio wants there to be a plus at the beginning of the phone number
        phone = '+' + phone

        message = client.messages \
                        .create(
                             body="Your department's order bundle for " + str(meal_name) + " for " + str(dept_name)
                             + " is ready for pickup",
                             from_=cfg.twilio_sendfrom,
                             to=phone
                         )
        if 'error' in message:
            print(message)
            slack_bot.send_message('bottesting', 'Error sending SMS message to ' + phone + '\r\n' + str(message))

    return
