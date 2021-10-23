import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import time

from config import cfg
import slack_bot


def send_message(recipients, dept_name, meal_name):
    """
    Send message to list of emails using Amazon AWS
    """
    SENDER = "noreply@food.magevent.net"
    SENDERNAME = "Staff Suite Orders"
    HOST = "email-smtp.us-east-1.amazonaws.com"
    PORT = 587

    SUBJECT = "Tuber Eats test email"
    BODY_TEXT = ("Your department's order bundle for " + str(meal_name) + " for " + str(dept_name)
                 + " is ready for pickup. \r\n"
                 "Please have someone come get it.  Thanks!\r\n \r\n"
                 "Staff Suite for 2022 is in room \r\n"
                 "For help finding Staff Suite or more information about it, please go to "
                 "")
    BODY_HTML = """<html>
    <body>
        <h1>Your department's order bundle for {dept} for {meal} is ready for pickup.</h1>
        <p>Please have someone come get it.  Thanks!</p>
        <p>Staff Suite for 2022 is in room </p>
        <p>For help finding Staff Suite or more information about it, please go to 
        <a href='notion.to'>Staff Suite Notion Page</a></p>
    </body>
    </html>""".format(dept=dept_name, meal=meal_name)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = SUBJECT
    msg['From'] = email.utils.formataddr((SENDERNAME, SENDER))
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
        try:
            for index, recipient in enumerate(recipients):
                if index % 5 == 0:
                    # every 5 emails waits 1 second, to avoid filling up the per-second sending limit for the AWS acct
                    time.sleep(1)
                msg['To'] = email
                server.sendmail(SENDER, email, msg.as_string())
        except Exception as e:
            print(e)
            print(recipients)
            slack_bot.send_message("bottesting", "Email message failed to send to " + str(recipient) + " from "
                                   + str(dept_name) + " for " + str(meal_name) + " \r\n" +
                                   e.response['Error']['Message'])
        server.close()

    except Exception as e:
        print(e)
        print(recipients)
        slack_bot.send_message("bottesting", "General error sending emails, not tied to a specific email address "
                               + " from " + str(dept_name) + " for " + str(meal_name) + " \r\n" + str(e))
    return
