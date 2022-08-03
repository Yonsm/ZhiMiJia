
from .zhimi_fan_v3 import *
from ..zhimi.entity import ZhiMiEntity, ZHIMI_SCHEMA
from homeassistant.components.fan import FanEntity, PLATFORM_SCHEMA, DIRECTION_REVERSE, DIRECTION_FORWARD, SUPPORT_PRESET_MODE, SUPPORT_PRESET_MODE, SUPPORT_DIRECTION, SUPPORT_OSCILLATE
from homeassistant.const import STATE_OFF, STATE_ON


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(ZHIMI_SCHEMA)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([ZhiMiFan(config)], True)


class ZhiMiFan(ZhiMiEntity, FanEntity):

    def __init__(self, conf):
        super().__init__(ALL_SVCS, conf)

    @property
    def supported_features(self):
        return SUPPORT_PRESET_MODE | SUPPORT_OSCILLATE | SUPPORT_DIRECTION

    async def async_poll(self):
        data = await super().async_poll()
        return data

    @property
    def state(self):
        return (STATE_OFF, STATE_ON)[self.data[Fan.Switch_Status]]

    @property
    def preset_modes(self):
        return ['档位' + str(i) for i in range(Fan_Fan_Level.MIN, Fan_Fan_Level.MAX + 1)]

    @property
    def preset_mode(self):
        return '档位' + str(self.data[Fan.Fan_Level])

    @property
    def oscillating(self):
        return self.data[Fan.Horizontal_Swing]

    @property
    def current_direction(self):
        return DIRECTION_FORWARD if self.data[Fan.Mode] == Fan_Mode.Straight_Wind else DIRECTION_REVERSE

    async def async_turn_on(self, speed, **kwargs):
        await self.async_control(Fan.Switch_Status, True)

    async def async_turn_off(self):
        await self.async_control(Fan.Switch_Status, False)

    async def async_set_preset_mode(self, preset_mode):
        await self.async_control(Fan.Fan_Level, preset_mode[2] if len(preset_mode) > 2 else preset_mode)

    async def async_oscillate(self, oscillating):
        await self.async_control(Fan.Horizontal_Swing, oscillating)

    async def async_set_direction(self, direction):
        await self.async_control(Fan.Mode, Fan_Mode.Straight_Wind if direction == DIRECTION_FORWARD else Fan_Mode.Natural_Wind)
