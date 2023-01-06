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

    # If people put new lines, or for some reason semicolons to separate phone numbers this converts them to commas
    phone_numbers = re.sub(r'[\r\n;]', ',', phone_numbers)
    phone_numbers = phone_numbers.split(',')

    for index, phone in enumerate(phone_numbers):
        if index % 5 == 4:
            time.sleep(5)

        original_phone = phone
        # remove hyphens and such from phone number
        phone = re.sub(r'[-,()\s.\+a-zA-Z]', '', phone)
        phone = phone.strip()
        if not phone:
            continue
            # skip anything that is blank after filtering out unwanted characters

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
            slack_bot.send_message('@wombat3', 'Error sending SMS message to ' + original_phone +
                                   '\r\nFor ' + str(meal_name) + " for " + str(dept_name) + '\r\n'
                                   + str(e))

    return
