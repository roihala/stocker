class ActivationCodes(object):
    # User registered to free trial and haven't paid yet
    TRIAL = 'trial'
    # Free trial has ended and user didn't register
    UNREGISTER = 'unregister'
    # User has started a subscription but haven't activated
    PENDING = 'pending'
    # User has an active subscription
    ACTIVE = 'active'
    # User has canceled the subscription
    CANCEL = 'cancel'
    # User has deregistered through the bot
    DEREGISTER = 'deregister'
