import random

import argon2
import codecs
import os
import secrets

import arrow
from pydantic import BaseModel
from starlette.middleware.wsgi import WSGIMiddleware
from telegram.utils import helpers

import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import uvicorn

from fastapi import FastAPI

from common_runnable import CommonRunnable
from src.rest.dilution import init_dash
from src.rest.wix_payload import WixPayLoad
from src.telegram_bot.resources.activation_kaki import ActivationCodes

NAME_TAG = 'STOCKER_NAME_TAG'
ACTIVATION_BUTTON_TAG = 'STOCKER_ACTIVATION_BUTTON_TAG'
PLAN_TAG = 'STOCKER_PLAN_TAG'


class Rest(CommonRunnable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if os.getenv("ENV") == "production":
            self.titan_mail = os.environ['TITAN_MAIL']
            self.titan_pass = os.environ['TITAN_PASS']
        else:
            self.titan_mail = self.args.titan_mail
            self.titan_pass = self.args.titan_pass

    def run(self):
        # app.mount("/dilution", WSGIMiddleware(dash_app.server))
        uvicorn.run(app)

    def create_parser(self):
        parser = super().create_parser()
        parser.add_argument('--titan_mail', dest='titan_mail', help='Titan email address', required=True)
        parser.add_argument('--titan_password', dest='titan_pass', help='Titan mail password', required=True)
        return parser


rest = Rest()
app = FastAPI()
# dash_app = init_dash(rest._mongo_db)


@app.post('/rest/a268c565c2242709165b17763ef6eace20a70345c26c2639ce78f28f18bb4d98')
async def subscription_activate(*, payload: WixPayLoad):
    __log_webhook(payload, 'subscription_activate')

    try:
        # Creating a unique token for the given email
        token = secrets.token_urlsafe()

        # Find available bot
        available_bot = __find_available_bot()

        email = payload.data.email
        create_user(email, available_bot, token, payload.data.order_id, payload.data.plan_name)

        name = payload.data.first_name + ' ' + payload.data.last_name

        __send_email(name, available_bot, payload.data.plan_name, email, token)

    except Exception as e:
        rest.logger.warning(f"Subscription activate failed for {payload.data.order_id}")
        rest.logger.error(e)


def create_user(email, available_bot, token, order_id, plan):
    ph = argon2.PasswordHasher()
    rest._mongo_db.telegram_users.insert_one(
        {'email': email,
         'order_id': order_id,
         'token': ph.hash(token),
         'date': arrow.utcnow().format(),
         'bot': available_bot,
         'activation': ActivationCodes.PENDING,
         'plan': plan})


def __send_email(name, available_bot, plan_title, receiver_email, token):
    rest.logger.info(f"Sending email to: {receiver_email}")

    password = rest.titan_pass
    sender_email = rest.titan_mail
    smtp_domain = "smtp.titan.email"
    activation_link = helpers.create_deep_linked_url(available_bot, token)

    # password = r'9qz*xFSTh&3588*'
    # sender_email = 'support@stocker.watch'
    # smtp_domain = "smtp.gmail.com"

    # Create a secure SSL context
    context = ssl.create_default_context()

    message = MIMEMultipart("alternative")
    message["Subject"] = "Stocker activation code"
    message["From"] = 'admin@stocker.watch'
    message["To"] = receiver_email

    # Create the plain-text and HTML version of your message
    text = f"""\
Hello {name},
We are happy to tell you that you can immediately start recieving our alerts, just click the link below:
{activation_link}

Please feel free to contact us at any matter, either by this mail or via telegram: http://t.me/EyesOnMarket"""

    with codecs.open(os.path.join(os.path.dirname(__file__), 'src/rest/activation_email.html')) as activation_email:
        html = activation_email.read() \
            .replace(NAME_TAG, name) \
            .replace(ACTIVATION_BUTTON_TAG, activation_link) \
            .replace(PLAN_TAG, plan_title)

    # Turn these into plain/html MIMEText objects
    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")

    message.attach(part1)
    message.attach(part2)

    # Port 465 for SSL
    with smtplib.SMTP_SSL(smtp_domain, 465, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())


def __find_available_bot():
    bot_users_counter = {bot.get('name'): 0 for bot in rest._mongo_db.bots.find()}

    for user in rest._mongo_db.bots.find({'bot': {'$exists': True}}):
        if user['bot'] not in bot_users_counter:
            rest.logger.warning(f"Invalid bot {user['bot']} found for user {user.get('user_name')}")
            continue

        bot_users_counter[user['bot']] += 1

    available_bots = [bot for bot, count in bot_users_counter.items() if count <= 30]
    return random.choice(available_bots) if available_bots else "stocker_alerts_bot"


@app.post('/rest/51eeea83393dec0b58dadc2e4abc81a2d60ce1ecd88e57d72b6626858520e3d7')
async def subscription_cancel(*, payload: WixPayLoad):
    __log_webhook(payload, 'subscription_cancel')

    rest.logger.info(f"Subscription cancel with payload: {payload.dict()}")
    try:
        # Handling wix's double cancel - they are sending many cancel messages to validate
        if 'activate_until' in rest._mongo_db.telegram_users.find_one({'order_id': payload.data.order_id}):
            pass

        result = rest._mongo_db.telegram_users.update_one({'order_id': payload.data.order_id},
                                                          {'$set': {'activation': ActivationCodes.CANCEL}})
        if result.modified_count != 1:
            raise ValueError("Couldn't cancel subscription")
    except Exception as e:
        rest.logger.warning(f"Subscription cancel failed for {payload.data.order_id}")
        rest.logger.error(e)


def __log_webhook(payload: BaseModel, webhook_type: str):
    data = payload.dict()
    rest.logger.info(f"{webhook_type} with payload: {data}")
    data.update({'date': arrow.utcnow().format(), 'type': webhook_type})
    rest._mongo_db.webhooks.insert_one(data)


if __name__ == "__main__":
    rest.run()
