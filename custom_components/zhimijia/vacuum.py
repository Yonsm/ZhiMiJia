from importlib import import_module
from homeassistant.components.vacuum import PLATFORM_SCHEMA
from ..zhimi.entity import ZHIMI_SCHEMA


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(ZHIMI_SCHEMA)


def setup_platform(hass, conf, add_entities, discovery_info=None):
    model = conf.get('model', 'viomi.washer.v13').replace('.', '_')
    module = import_module('.vacuum_' + model, __package__)
    ZhiMiVacuum = getattr(module, 'ZhiMiVacuum')
    add_entities([ZhiMiVacuum(hass, conf)], True)
