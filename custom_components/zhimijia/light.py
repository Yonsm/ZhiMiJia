
from homeassistant.components.light import LightEntity, PLATFORM_SCHEMA, ATTR_BRIGHTNESS, ColorMode
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from math import ceil
from ..zhimi.entity import ZhiMiEntity, ZHIMI_SCHEMA

import logging
_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(ZHIMI_SCHEMA | {
    vol.Optional('power_prop', default='power'): cv.string,
    vol.Optional('power_on'): object,
    vol.Optional('power_off'): object,
    vol.Optional('brightness_prop'): cv.string,
})


async def async_setup_platform(hass, conf, async_add_entities, discovery_info=None):
    async_add_entities([ZhiMiLight(hass, conf)], True)


class ZhiMiLight(ZhiMiEntity, LightEntity):

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}        

    def __init__(self, hass, conf):
        self.power_prop = conf['power_prop']
        self.brightness_prop = conf.get('brightness_prop')
        miot = self.power_prop[0].isdigit()
        self.power_on = conf.get('power_on', True if miot else 'on')
        self.power_off = conf.get('power_off', False if miot else 'off')
        props = [self.power_prop]
        if self.brightness_prop is not None:
            props.append(self.brightness_prop)
            #self._attr_supported_color_modes = {ColorMode.ONOFF, ColorMode.BRIGHTNESS}
        super().__init__(hass, props, conf)

    @property
    def brightness(self):
        return (self.data[self.brightness_prop] * 255 / 100) if self.brightness_prop is not None else 100

    @property
    def is_on(self):
        return self.data[self.power_prop] == self.power_on

    async def async_turn_on(self, **kwargs):
        if ATTR_BRIGHTNESS in kwargs and self.brightness_prop is not None:
            brightness = kwargs[ATTR_BRIGHTNESS]
            percent_brightness = ceil(100 * brightness / 255.0)
            if await self.async_control(self.brightness_prop, percent_brightness):
                self.data[self.brightness_prop] = percent_brightness
        else:
            await self.async_control(self.power_prop, self.power_on)

    async def async_turn_off(self, **kwargs):
        await self.async_control(self.power_prop, self.power_off)
