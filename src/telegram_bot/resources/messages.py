from src.alert.alerter_base import AlerterBase


class Messages(object):
    CHECK_MARK_EMOJI_UNICODE = u'\U00002705'
    HEART_EMOJI_UNICODE = u'\U00002764'
    PUNCH_EMOJI_UNICODE = u'\U0001F44A'

    WELCOME_MESSAGE = f"""Welcome to Stocker alerts, here's a quick how-to guide: 
1. The main part - our alerts: 
{AlerterBase.RED_CIRCLE_EMOJI_UNICODE} Means old value
{AlerterBase.GREEN_CIRCLE_EMOJI_UNICODE} Means new value

2. Our tools:
You may use them in different ways, the most popular is through /tools command.
For the more technical of you - there's a list of our supported commands in /start command
e.g:
/dilution SOAN
/alerts ggii

\* *Alerts will start popping in this chat*

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
/otciq - View Otciq access status for a given ticker.
"""

    UNREGISTERED = 'You need to be registered in order to use this. Join our free trial for more info!'

    # Survey messages
    INVALID_WATCHLIST = 'Invalid watchlist, please insert a list of tickers separated by comma (,) AND NOTHING ELSE e.g:\n' \
                        'GGII,DRGV,SOAN,RSHN'

    SURVEY_END = 'Survey has ended, thanks and good luck!'
    REMINDER_MESSAGE = """{punch_emoji} Dear user,
Your free trial {formatted_time}.
    
Check our website for pricing plans and more info."""
