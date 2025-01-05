from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import re
import smtplib
import time

from config import cfg
import slack_bot


def send_message(recipients, dept_name, meal_name):
    """
    Send message to list of emails using Amazon AWS
    """
    errors = ""
    recipients = re.sub(r'[\r\n; ]', ',', recipients)
    recipients = recipients.split(',')

    SENDER = "noreply@food.magevent.net"
    SENDERNAME = "Staff Suite Orders"
    HOST = "email-smtp.us-east-1.amazonaws.com"
    PORT = 587

    SUBJECT = "Staff Suite Order Ready"
    BODY_TEXT = ("Your department's order bundle for " + str(meal_name) + " for " + str(dept_name)
                 + " is ready for pickup. \r\n"
                 "Please have someone come get it.  Thanks!\r\n \r\n"
                 "Staff Suite for 2022 is in " + cfg.room_location + " \r\n"
                 "For help finding Staff Suite or more information about it, please go to " +
                 cfg.location_url)
    BODY_HTML = """<html>
    <body>
        <h1>Your department's order bundle for {dept} for {meal} is ready for pickup.</h1>
        <p>Please have someone come get it.  Thanks!</p>
        <p>Staff Suite for 2022 is in {room}</p>
        <p>For help finding Staff Suite or more information about it, please go to 
        <a href="{url}">Staff Suite's Notion Page</a></p>
    </body>
    </html>""".format(dept=dept_name, meal=meal_name, room=cfg.room_location, url=cfg.location_url)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = SUBJECT
    msg['From'] = formataddr((SENDERNAME, SENDER))
    part1 = MIMEText(BODY_TEXT, 'plain')
    part2 = MIMEText(BODY_HTML, 'html')
    msg.attach(part1)
    msg.attach(part2)

    try:
        server = smtplib.SMTP(HOST, PORT)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(cfg.aws_authuser, cfg.aws_authkey)
        for index, recipient in enumerate(recipients):
            if index % 5 == 4:
                # every 5 emails waits 1 second, to avoid filling up the per-second sending limit for the AWS acct
                time.sleep(1)
            recipient.strip()
            if not recipient:
                # if recipient blank after processing, skip trying to send to it
                continue
            msg['To'] = recipient
            try:
                server.sendmail(SENDER, recipient, msg.as_string())
            except (smtplib.SMTPResponseException, smtplib.SMTPRecipientsRefused) as e:
                slack_bot.send_message("@Wombat3", "Email message failed to send to " + str(recipient) + " from "
                                       + str(dept_name) + " for " + str(meal_name) + " \r\n" +
                                       str(e))
        server.close()

    except Exception as e:
        error = ("General error sending emails, not tied to a specific email address"
                 + " from " + str(dept_name) + " for " + str(meal_name) +
                 " \r\n" + str(e) + " \r\n" + str(type(e)))
        slack_bot.send_message("@Wombat3", error)
        errors = errors + error + "\r\n"

    return errors
