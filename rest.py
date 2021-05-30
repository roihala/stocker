import codecs
import os

from cryptography.fernet import Fernet

import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


import uvicorn

from fastapi import FastAPI

from runnable import Runnable
from src.rest.dilution import init_dash
from src.rest.wix_payload import WixPayload


NAME_TAG = 'STOCKER_NAME_TAG'
ACTIVATION_BUTTON_TAG = 'STOCKER_ACTIVATION_BUTTON_TAG'
PLAN_TAG = 'STOCKER_PLAN_TAG'


class Rest(Runnable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if os.getenv("ENV") == "production":
            self.titan_mail = os.environ['TITAN_MAIL']
            self.titan_pass = os.environ['TITAN_PASS']
            self.stocker_key = os.environ['STOCKER_KEY']
        else:
            self.titan_mail = self.args.titan_mail
            self.titan_pass = self.args.titan_pass
            self.stocker_key = self.args.stocker_key

    def run(self):
        # update_dash(dash_app)
        # app.mount("/dilution", WSGIMiddleware(dash_app.server))
        uvicorn.run(app)

    def create_parser(self):
        parser = super().create_parser()
        parser.add_argument('--titan_mail', dest='titan_mail', help='Titan email address', required=True)
        parser.add_argument('--titan_password', dest='titan_pass', help='Titan mail password', required=True)
        parser.add_argument('--stocker_key', dest='stocker_key', help='Stocker secret key', required=True)
        return parser


rest = Rest()
app = FastAPI()
dash_app = init_dash(rest._mongo_db)


@app.get('/rest')
async def root():
    return {'success': True}


@app.post('/rest/a268c565c2242709165b17763ef6eace20a70345c26c2639ce78f28f18bb4d98')
async def subscription_activate(*, payload: WixPayload):
    # we will be encryting the below string.
    email = payload.data.contact_email

    key = rest.stocker_key
    activation_code = Fernet(key).encrypt(email.encode())

    name = payload.data.contact_first_name + ' ' + payload.data.contact_last_name

    __send_email(name, payload.data.plan_title, email,generate_activation_link(activation_code))


@app.post('/rest/51eeea83393dec0b58dadc2e4abc81a2d60ce1ecd88e57d72b6626858520e3d7')
async def subscription_cancel():
    pass


def __send_email(name, plan_title, receiver_email, activation_link):
    password = rest.titan_pass
    sender_email = rest.titan_mail
    smtp_domain = "smtp.titan.email"

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
        html = activation_email.read()\
            .replace(NAME_TAG, name)\
            .replace(ACTIVATION_BUTTON_TAG, activation_link)\
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


def generate_activation_link(activation_code):
    return 'https://stocker.watch'


if __name__ == "__main__":
    rest.run()
