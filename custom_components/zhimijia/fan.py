#from .zhimi_fan_v3 import *
from importlib import import_module
from ..zhimi.entity import ZhiMiEntity, ZHIMI_SCHEMA
from homeassistant.components.fan import FanEntity, PLATFORM_SCHEMA, DIRECTION_REVERSE, DIRECTION_FORWARD, SUPPORT_PRESET_MODE, SUPPORT_PRESET_MODE, SUPPORT_DIRECTION, SUPPORT_OSCILLATE
from homeassistant.const import STATE_OFF, STATE_ON


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(ZHIMI_SCHEMA)

ALL_PROPS = {
    'zhimi.fan': ('power', 'angle', 'angle_enable', 'poweroff_time', 'speed_level', 'natural_level', 'child_lock', 'led_b', 'buzzer'),
    'zhimi.fan.v3': ('zhimi.fan', ('battery', 'temp_dec', 'humidity')),
    'zhimi.fan.za3': ('zhimi.fan')
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    model = config.get('model', 'zhimi.fan')
    if model in ALL_PROPS:
        props = [x for x in ALL_PROPS[model] for x in (ALL_PROPS[x] if isinstance(x, str) else x)]
        entity = ZhiMiIOFan(props, config)
    else:
        module = import_module('.' + model.replace('.', '_'), __package__)
        globals().update({x: getattr(module, x) for x in module.__dict__ if not x.startswith('_')})
        entity = ZhiMIoTFan(ALL_SVCS, config)
    async_add_entities([entity], True)


class ZhiMIoTFan(ZhiMiEntity, FanEntity):

    @property
    def supported_features(self):
        return SUPPORT_PRESET_MODE | SUPPORT_OSCILLATE | SUPPORT_DIRECTION

    @property
    def state(self):
        return STATE_ON if self.data[Fan.Switch_Status] else STATE_OFF

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

    async def async_turn_on(self, speed=None, percentage=None,  preset_mode=None, **kwargs):
        await self.async_control(Fan.Switch_Status, True)

    async def async_turn_off(self):
        await self.async_control(Fan.Switch_Status, False)

    async def async_set_preset_mode(self, preset_mode):
        await self.async_control(Fan.Level, int(preset_mode[2] if len(preset_mode) > 2 else preset_mode))

    async def async_oscillate(self, oscillating):
        await self.async_control(Fan.Horizontal_Swing, oscillating)

    async def async_set_direction(self, direction):
        await self.async_control(Fan.Mode, Fan_Mode.Natural_Wind if direction == DIRECTION_REVERSE else Fan_Mode.Straight_Wind)


class ZhiMiIOFan(ZhiMiEntity, FanEntity):

    @property
    def supported_features(self):
        return SUPPORT_PRESET_MODE | SUPPORT_OSCILLATE | SUPPORT_DIRECTION

    @property
    def device_state_attributes(self):
        return {('temperature' if k == 'temp_dec' else k): ((v/10) if k == 'temp_dec' else v) for k, v in super().device_state_attributes.items()}

    @property
    def state(self):
        return self.data['power']

    @property
    def preset_modes(self):
        return ['档位' + str(i) for i in range(1, 5)]

    @property
    def preset_mode(self):
        return '档位' + str(int((self.data['speed_level'] + 24) / 25))

    @property
    def oscillating(self):
        return self.data['angle_enable'] == 'on'

    @property
    def current_direction(self):
        return DIRECTION_REVERSE if self.data['natural_level'] else DIRECTION_FORWARD

    async def async_turn_on(self, speed=None, percentage=None,  preset_mode=None, **kwargs):
        await self.async_control('power', 'on')

    async def async_turn_off(self):
        await self.async_control('power', 'off')

    async def async_set_preset_mode(self, preset_mode):
        level = int(preset_mode[2] if len(preset_mode) > 2 else preset_mode)
        await self.async_control('speed_level', level * 25)

    async def async_oscillate(self, oscillating):
        await self.async_control('angle' if oscillating else 'angle_enable', 30 if oscillating else 'off', ignore_prop=True)

    async def async_set_direction(self, direction):
        await self.async_control('natural_level' if direction == DIRECTION_REVERSE else 'speed_level', self.data['speed_level'], ignore_prop=True)
