import logging

log = logging.getLogger("samaj.sms")


def send_sms(mobile_e164: str, text: str):
    # ponytail: dev-only console sender. The SMS gateway (provider still to be chosen) replaces this body
    # before any real deployment -- printing OTPs anywhere but a dev machine is a security hole.
    log.warning("SMS to %s: %s", mobile_e164, text)
