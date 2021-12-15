import time
import re

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

import slack_bot
from config import cfg


def send_message(phone_numbers, dept_name, meal_name):
    """
    Sends message to list of phone numbers
    """
    client = Client(cfg.twilio_authkey, cfg.twilio_authsecret, cfg.twilio_account_sid)

    for index, phone in enumerate(phone_numbers):
        if index % 5 == 0:
            time.sleep(5)
        # remove hyphens and such from phone number
        phone = re.sub(r'[-,()\.\+a-zA-Z]', '', phone)

        # if US number without 1 for country code at beginning of number then add it
        # I think this should ignore if someone has given an international number, at least in most cases.
        if len(phone) == 10:
            phone = '1' + phone

        # Twilio wants there to be a plus at the beginning of the phone number
        phone = '+' + phone
        try:
            message = client.messages \
                            .create(
                                 body="Your department's order bundle for " + str(meal_name) + " for " + str(dept_name)
                                 + " is ready for pickup",
                                 from_=cfg.twilio_sendfrom,
                                 to=phone
                             )

        except TwilioRestException as e:
            print("-----------twilio exception processing--------------")
            print(e)
            slack_bot.send_message('bottesting', 'Error sending SMS message to ' + phone + '\r\n')
            print("-----------end twilio exception processing--------------")

    return
