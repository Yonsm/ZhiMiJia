import logging
import time
import datetime

from miio import Device

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.components.fan import FanEntity, SUPPORT_SET_SPEED, SUPPORT_OSCILLATE, SUPPORT_DIRECTION, PLATFORM_SCHEMA
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)


APPOINT_MIN = 1  # 3 in app default
APPOINT_MAX = 23  # 19 in app default
DEFAULT_DRY_MODE = 30721 # 
DEFAULT_APPOINT_TIME = -8 # -8 means 8 o'clock, 8 means 8 hours later

WASHER_PROPS = [
    "program",
    "wash_process",
    "wash_status",
    # "water_temp",
    # "rinse_status",
    # "spin_level",
    "remain_time",
    "appoint_time",
    # "be_status",
    # "run_status",
    "DryMode",
    # "child_lock",
]


WASHER_PROGS = {
    'goldenwash': '黄金洗',
    'quick': '快洗',
    'super_quick': '超快洗',

    'antibacterial': '除菌洗',
    'refresh': '空气洗',

    'dry': '黄金烘',
    'weak_dry': '低温烘',

    'rinse_spin': '漂+脱',
    'spin': '单脱水',
    'drumclean': '筒清洁',

    'cottons': '棉织物',
    'down': '羽绒服',
    'wool': '羊毛',
    'shirt': '衬衣',
    'jeans': '牛仔',
    'underwears': '内衣',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the light from config."""
    host = config[CONF_HOST]
    token = config[CONF_TOKEN]
    name = config.get(CONF_NAME)
    add_entities([VioMiWasher(name, host, token)], True)


class VioMiWasher(FanEntity, RestoreEntity):

    def __init__(self, name, host, token):
        self._name = name or host
        self._device = Device(host, token)
        self._status = {'dash_extra_forced': True,
                        'genie_deviceType': 'washmachine'}
        self._state = None
        self._skip_update = False
        self._dry_mode = 0
        self._appoint_time = 0

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        _LOGGER.debug("async_added_to_hass: %s", last_state)
        if last_state:
            self._appoint_time = int(last_state.attributes.get('direction') == 'reverse')
            self._dry_mode = int(last_state.attributes.get('oscillating', 0))
            _LOGGER.debug("Restore state: dry_mode=%s, appoint_time=%s", self._dry_mode, self._appoint_time)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_SET_SPEED | SUPPORT_OSCILLATE | SUPPORT_DIRECTION

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return 'mdi:washing-machine'

    @property
    def available(self):
        """Return true when state is known."""
        return self._state is not None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._status

    def update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        status = self._status
        try:
            for prop in WASHER_PROPS:
                status[prop] = self._device.send('get_prop', [prop])[0]
            self._state = status['wash_status'] == 1 and (
                (status['wash_process'] > 0 and status['wash_process'] < 7) or status['appoint_time'] != 0)
        except Exception as exc:
            _LOGGER.error("Error on update: %s", exc)
            self._state = None

        if self._state:  # Update dash name for status
            dash_name = '剩' + str(status['remain_time']) + '分'
            appoint_time = status['appoint_time']
            if appoint_time:
                dash_name += '/' + str(appoint_time) + '时'
            if status['DryMode']:
                dash_name += '+烘'
            self._status['dash_name'] = dash_name
        elif 'dash_name' in status:
            del status['dash_name']

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, speed=None, **kwargs):
        """Turn the device on."""
        _LOGGER.debug('turn_on: speed=%s, kwargs=%s', speed, kwargs)

        # Turn up
        if speed:
            self.set_speed(speed)
        else:
            self.set_wash_program(self._status.get('program') or 'goldenwash')
        time.sleep(1)

        # Set dry mode
        dry_mode = DEFAULT_DRY_MODE if self._dry_mode == 1 else self._dry_mode
        if self._status.get('DryMode') != dry_mode:
            if not self.control("SetDryMode", dry_mode):
                return
            time.sleep(1)

        # Calc appoint time
        appoint_time = self._appoint_time
        if appoint_time < 0:
            appoint_clock = -appoint_time
            now = datetime.datetime.now()
            hour = now.hour
            if now.minute > 10:
                hour += 1
            if hour <= appoint_clock - APPOINT_MIN:
                appoint_time = appoint_clock - hour
            elif hour >= appoint_clock + 24 - APPOINT_MAX:
                appoint_time = appoint_clock + 24 - hour
            else:
                appoint_time = 0

        if self.control('set_appoint_time' if appoint_time else 'set_wash_action', appoint_time or 1):
            self._state = True
            self._skip_update = True

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self.control('set_wash_action', 2):
            self._state = False
            self._skip_update = True

    @property
    def speed_list(self):
        """Get the list of available speeds."""
        return list(WASHER_PROGS.values())

    @property
    def speed(self):
        """Return the current speed."""
        return WASHER_PROGS.get(self._status.get('program'))

    def set_speed(self, speed):
        """Set the speed of the fan."""
        _LOGGER.debug('set_speed: %s', speed)

        for program in WASHER_PROGS:
            if program == speed or WASHER_PROGS[program] == speed:
                self.set_wash_program(program)
                return

        for control in speed.split(','):
            params = control.split('=')
            if len(params) == 2:
                if params[0] == 'program' or params[0] == 'set_wash_program':
                    if not self.set_wash_program(params[1]):
                        return
                elif params[0] == 'dry_mode':
                    # self.oscillate(params[1])
                    self._dry_mode = int(params[1])
                elif params[0] == 'appoint_time':
                    # self.set_direction(params[1])
                    self._appoint_time = int(params[1])
                elif params[0] == 'appoint_clock':
                    # self.set_direction('-' + params[1])
                    self._appoint_time = -int(params[1])
                elif not self.control(params[0], params[1]):  # Custom command
                    return
            else:
                _LOGGER.error("Invalid speed format:%s", params)

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return bool(self._dry_mode)

    def oscillate(self, oscillating):
        """Oscillate the fan."""
        self._dry_mode = int(oscillating)
        _LOGGER.debug("oscillate: dry_mode=%s", self._dry_mode)

    @property
    def current_direction(self):
        """Return the current direction of the fan."""
        return 'reverse' if self._appoint_time else 'forward'

    def set_direction(self, direction):
        """Set the direction of the fan."""
        self._appoint_time = DEFAULT_APPOINT_TIME if direction == 'reverse' else int(direction)
        _LOGGER.debug("set_direction: appoint_time=%s", self._appoint_time)

    def control(self, name, value):
        _LOGGER.debug('Waher control: %s=%s', name, value)
        try:
            return self._device.send(name, [value]) == ['ok']
        except Exception as exc:
            _LOGGER.error("Error on control: %s", exc)
            return None

    def set_wash_program(self, program):
        if self.control('set_wash_program', program):
            self._status['program'] = program
            self._skip_update = True
            return True
        return False
