import boto3
from botocore.exceptions import ClientError

import slack_bot


def send_message(RECIPIENT, dept_name, meal_name):
    """
    Send email message using Amazon AWS
    """
    SENDER = "noreply@food.magevent.net"
    AWS_REGION = "us-east-1"
    CHARSET = "UTF-8"
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

    client = boto3.client('ses', region_name=AWS_REGION)

    try:
        response = client.send_email(
            Destination={'ToAddresses': [RECIPIENT, ], },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': BODY_HTML,
                    },
                    'Text': {
                        'Charset': CHARSET,
                        'Data': BODY_TEXT,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER
        )

    except ClientError as e:
        print(e.response['Error']['Message'])
        slack_bot.send_message("bottesting", "Email message failed to send to " + str(RECIPIENT) + " from "
                               + str(dept_name) + " for " + str(meal_name) + " \r\n" +
                               e.response['Error']['Message'])
    return
