from importlib import import_module
from ..zhimi.entity import ZhiMiEntity, ZHIMI_SCHEMA
from homeassistant.components.fan import FanEntity, PLATFORM_SCHEMA, DIRECTION_REVERSE, DIRECTION_FORWARD, SUPPORT_PRESET_MODE, SUPPORT_PRESET_MODE, SUPPORT_DIRECTION, SUPPORT_OSCILLATE
from homeassistant.const import STATE_OFF, STATE_ON


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(ZHIMI_SCHEMA)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    module = import_module('.' + config.get('model', 'zhimi.fan.v3').replace('.', '_'), __package__)
    globals().update({x: getattr(module, x) for x in module.__dict__ if not x.startswith('_')})
    async_add_entities([ZhiMiFan(config)], True)


class ZhiMiFan(ZhiMiEntity, FanEntity):

    def __init__(self, conf):
        super().__init__(ALL_SVCS, conf)

    @property
    def supported_features(self):
        return SUPPORT_PRESET_MODE | SUPPORT_OSCILLATE | SUPPORT_DIRECTION

    @property
    def state(self):
        return (STATE_OFF, STATE_ON)[self.data[Fan.Switch_Status]]

    @property
    def preset_modes(self):
        return ['档位' + str(i) for i in range(Fan_Level.MIN, Fan_Level.MAX + 1)]

    @property
    def preset_mode(self):
        return '档位' + str(self.data[Fan.Level])

    @property
    def oscillating(self):
        return self.data[Fan.Horizontal_Swing]

    @property
    def current_direction(self):
        return DIRECTION_REVERSE if self.data.get(Fan.Mode) == Fan_Mode.Natural_Wind else DIRECTION_FORWARD

    async def async_turn_on(self, speed, **kwargs):
        await self.async_control(Fan.Switch_Status, True)

    async def async_turn_off(self):
        await self.async_control(Fan.Switch_Status, False)

    async def async_set_preset_mode(self, preset_mode):
        await self.async_control(Fan.Level, preset_mode[2] if len(preset_mode) > 2 else preset_mode)

    async def async_oscillate(self, oscillating):
        await self.async_control(Fan.Horizontal_Swing, oscillating)

    async def async_set_direction(self, direction):
        await self.async_control(Fan.Mode, Fan_Mode.Natural_Wind if direction == DIRECTION_REVERSE else Fan_Mode.Straight_Wind)
