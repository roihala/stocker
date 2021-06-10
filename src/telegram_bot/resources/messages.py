from src.alert.alerter_base import AlerterBase


class Messages(object):
    CHECK_MARK_EMOJI_UNICODE = u'\U00002705'
    HEART_EMOJI_UNICODE = u'\U00002764'
    PUNCH_EMOJI_UNICODE = u'\U0001F44A'

    WELCOME_MESSAGE = f"""Welcome to Stocker alerts, here's a quick how-to guide: 
1. The main part - our alerts:
From now on you will start getting alerts to this chat where: 
{AlerterBase.RED_CIRCLE_EMOJI_UNICODE} Means old value
{AlerterBase.GREEN_CIRCLE_EMOJI_UNICODE} Means new value

2. Our tools:
You may use them in different ways, the most popular is through /tools command.
For the more technical of you - there's a list of our supported commands in /start command
e.g:
/dilution SOAN
/alerts ggii

Good luck {HEART_EMOJI_UNICODE}"""

    LAUNCH_MESSAGE = """Dear users {PUNCH_EMOJI_UNICODE} 
I'm excited to tell you that great things are happening, and the greatest among them started because of your feedbacks, so thank you guys, *you are all marked as VIP users* {HEART_EMOJI_UNICODE}

Starting from today, Stocker Alerts will not remain a free bot in order to allow those great things to happen. 
But for now, you can just click on free trial to get ADDITIONAL TWO WEEKS of free usage

Love you all and please keep sending us feedbacks, *we won't bite*"""

    START_MESSAGE = """
The following commands will make me sing:

/tools - User friendly interface for reaching our tools.
/deregister - Do this to stop getting alerts from stocker. *not recommended*.
/alerts - Resend previously detected alerts for a given ticker.
/dilution - A graph of changes in AS/OS/unrestricted over time.
/info - View the LATEST information for a given ticker.
"""
