"""Constants for the Bose integration."""

import logging

DOMAIN = "bose"

# Token Refresh Delay is how long between each check if the token is valid
# Token Retry Delay is how long before each retry if refresh fails
TOKEN_REFRESH_DELAY = 3600  # seconds
TOKEN_RETRY_DELAY = 120  # seconds

# Options key for Chromecast auto-enable setting
CONF_CHROMECAST_AUTO_ENABLE = "chromecast_auto_enable"


_LOGGER = logging.getLogger("bose")
