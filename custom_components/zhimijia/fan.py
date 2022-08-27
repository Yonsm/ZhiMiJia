#from .zhimi_fan_v3 import *
from ..zhimi.entity import ZhiMiEntity, ZHIMI_SCHEMA
from homeassistant.components.fan import FanEntity, PLATFORM_SCHEMA, DIRECTION_REVERSE, DIRECTION_FORWARD, SUPPORT_SET_SPEED, SUPPORT_PRESET_MODE, SUPPORT_DIRECTION, SUPPORT_OSCILLATE
from homeassistant.const import STATE_OFF, STATE_ON


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(ZHIMI_SCHEMA)

ALL_PROPS = {
    'zhimi.fan.za3': ['power', 'angle', 'angle_enable', 'poweroff_time', 'speed_level', 'natural_level', 'child_lock', 'led_b', 'buzzer'],
    'zhimi.fan.v3': ['power', 'angle', 'angle_enable', 'poweroff_time', 'speed_level', 'natural_level', 'child_lock', 'led_b', 'buzzer', 'battery', 'temp_dec', 'humidity'],
    'zhimi.airfresh.va2': ['power', 'mode', 'aqi', 'temp_dec', 'humidity', 'co2', 'f1_hour_used', 'child_lock', 'buzzer', 'led_level'],
    'zhimi.airpurifier.m1': ['power', 'mode', 'aqi', 'average_aqi', 'temp_dec', 'humidity', 'favorite_level', 'f1_hour_used', 'child_lock', 'buzzer', 'bright', 'filter1_life', 'use_time', 'motor1_speed', 'purify_volume'],
}

ALL_MODES = {
    'zhimi.airpurifier.m1': {'auto': '自动', 'silent': '静音', 'favorite': '最爱'},
    'zhimi.airfresh.va2': {'auto': '自动', 'silent': '静音', 'interval': '间歇', 'low': '低档', 'middle': '中档', 'strong': '高档'},
}


async def async_setup_platform(hass, conf, async_add_entities, discovery_info=None):
    model = conf.get('model', 'zhimi.fan')
    if model in ALL_PROPS:
        entity = ZhiMiIOFan(hass, ALL_PROPS[model], conf)
        entity.model = model
    else:
        from importlib import import_module
        module = import_module('.' + model.replace('.', '_'), __package__)
        globals().update({x: getattr(module, x) for x in module.__dict__ if not x.startswith('_')})
        entity = ZhiMIoTFan(hass, ALL_SVCS, conf)
    async_add_entities([entity], True)


class ZhiMIoTFan(ZhiMiEntity, FanEntity):

    @property
    def supported_features(self):
        features = 0
        # if hasattr(Fan, 'Speed'):
        #     features |= SUPPORT_SET_SPEED
        if hasattr(Fan, 'Level'):
            features |= SUPPORT_PRESET_MODE
        if hasattr(Fan, 'Horizontal_Swing'):
            features |= SUPPORT_OSCILLATE
        if hasattr(Fan_Mode, 'Natural_Wind'):
            features |= SUPPORT_DIRECTION
        return features

    @property
    def state(self):
        return STATE_ON if self.data[Fan.Switch_Status] else STATE_OFF

    async def async_turn_on(self, speed=None, percentage=None,  preset_mode=None, **kwargs):
        await self.async_control(Fan.Switch_Status, True)

    async def async_turn_off(self):
        await self.async_control(Fan.Switch_Status, False)

    @property
    def preset_modes(self):
        return ['档位' + str(i) for i in range(Fan_Level.MIN, Fan_Level.MAX + 1)]

    @property
    def preset_mode(self):
        return '档位' + str(self.data[Fan.Level])

    async def async_set_preset_mode(self, preset_mode):
        await self.async_control(Fan.Level, int(preset_mode[2] if len(preset_mode) > 2 else preset_mode))

    @property
    def oscillating(self):
        return self.data[Fan.Horizontal_Swing]

    async def async_oscillate(self, oscillating):
        await self.async_control(Fan.Horizontal_Swing, oscillating)

    @property
    def current_direction(self):
        return DIRECTION_REVERSE if self.data.get(Fan.Mode) == Fan_Mode.Natural_Wind else DIRECTION_FORWARD

    async def async_set_direction(self, direction):
        await self.async_control(Fan.Mode, Fan_Mode.Natural_Wind if direction == DIRECTION_REVERSE else Fan_Mode.Straight_Wind)


class ZhiMiIOFan(ZhiMiEntity, FanEntity):

    @property
    def supported_features(self):
        features = 0
        if 'speed_level' in self.props or 'favorite_level' in self.props:
            features |= SUPPORT_SET_SPEED
        if 'mode' in self.props or 'speed_level' in self.props:
            features |= SUPPORT_PRESET_MODE
        if 'angle' in self.props:
            features |= SUPPORT_OSCILLATE
        if 'natural_level' in self.props:
            features |= SUPPORT_DIRECTION
        return features

    @property
    def state(self):
        return self.data['power']

    async def async_turn_on(self, speed=None, percentage=None,  preset_mode=None, **kwargs):
        await self.async_control('power', 'on')

    async def async_turn_off(self):
        await self.async_control('power', 'off')

    @property
    def percentage(self):
        return self.data['favorite_level'] * 10 if 'favorite_level' in self.props else self.data['speed_level']

    async def async_set_percentage(self, percentage):
        if percentage == 0:
            await self.async_turn_off()
        elif 'favorite_level' in self.props:
            await self.async_control('favorite_level', int((percentage + 9) / 10), alias_prop='level_favorite')
            await self.async_control('mode', 'favorite')
        else:
            await self.async_control('speed_level', percentage)

    @property
    def preset_modes(self):
        if self.model in ALL_MODES:
            return list(ALL_MODES[self.model].values())
        return ['档位' + str(i) for i in range(1, 5)]

    @property
    def preset_mode(self):
        if self.model in ALL_MODES:
            return ALL_MODES[self.model][self.data['mode']]
        return '档位' + str(int((self.data['speed_level'] + 24) / 25))

    async def async_set_preset_mode(self, preset_mode):
        if self.model in ALL_MODES:
            modes = ALL_MODES[self.model]
            preset_modes = list(modes.values())
            return await self.async_control('mode', list(modes.keys())[preset_modes.index(preset_mode)] if preset_mode in preset_modes else preset_mode)
        level = int(preset_mode[2] if len(preset_mode) > 2 else preset_mode)
        await self.async_control('speed_level', level * 25)

    @property
    def oscillating(self):
        return self.data['angle_enable'] == 'on'

    async def async_oscillate(self, oscillating):
        await self.async_control('angle' if oscillating else 'angle_enable', 30 if oscillating else 'off', ignore_prop=True)

    @property
    def current_direction(self):
        return DIRECTION_REVERSE if self.data['natural_level'] else DIRECTION_FORWARD

    async def async_set_direction(self, direction):
        await self.async_control('natural_level' if direction == DIRECTION_REVERSE else 'speed_level', self.data['speed_level'], ignore_prop=True)
