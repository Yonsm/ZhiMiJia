from importlib import import_module
from homeassistant.components.vacuum import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_TOKEN
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import logging

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required('model'): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    vol.Optional('did'): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    module = import_module('.vacuum_' + config['model'], __package__)
    if CONF_NAME in config and CONF_HOST in config:
        ZhiViomiWasher = getattr(module, 'ZhiViomiWasher')
        add_entities([ZhiViomiWasher(config)], True)
    elif 'did' in config:
        ZhiViomiCloudWasher = getattr(module, 'ZhiViomiCloudWasher')
        add_entities([ZhiViomiCloudWasher(config)], True)
    else:
        _LOGGER.error('Need %s/%s or did.', CONF_HOST, CONF_TOKEN)
