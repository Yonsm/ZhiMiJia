from .viomi_washer_v5 import *
from ..zhimi import miio_service
from .entity import ZhiPollEntity

from homeassistant.components.vacuum import PLATFORM_SCHEMA, SUPPORT_CLEAN_SPOT, SUPPORT_FAN_SPEED, SUPPORT_LOCATE, SUPPORT_PAUSE, SUPPORT_RETURN_HOME, SUPPORT_SEND_COMMAND, SUPPORT_START, SUPPORT_STATUS, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON, VacuumEntity
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_TOKEN
from miio import Device
import datetime
import homeassistant.helpers.config_validation as cv
import logging
from asyncio import sleep
import voluptuous as vol


_LOGGER = logging.getLogger(__name__)

APPOINT_MIN = 1  # 3 in app default
APPOINT_MAX = 23  # 19 in app default
DEFAULT_DRY_MODE = 30721
DEFAULT_APPOINT_TIME = -8  # -8 means 8 o'clock, 8 means 8 hours later

PROP_Paused = 0
PROP_Dry_Mode = 7
PROP_Appoint_Time = 8


class WASH_State(IntEnum):
    Idle = 0
    Washing1 = 1
    Washing2 = 2
    Washing3 = 3
    Washing4 = 4
    Washing5 = 5
    Fault = 6
    Off = 7
    Busy = 8
    Unknown = 9


PROP_NAMES = {
    'wash_status': '暂停状态',
    'child_lock': '按键锁定',
    'wash_process': '洗涤阶段',
    'program': '洗涤模式',
    'remain_time': '剩余时间',
    'water_temp': '洗涤水温',
    'spin_level': '脱水转速',
    'DryMode': '烘干模式',
    'appoint_time': '预约时间',
    # 'be_status',
    # 'run_status',
    # 'rinse_status',
}

MODE_NAMES = {
    'dry': '黄金烘',
    'weak_dry': '低温烘',
    'refresh': '空气洗',
    'goldenwash': '黄金洗',
    'super_quick': '超快洗',
    'cottons': '棉织物',
    'wool': '羊毛',
    'down': '羽绒服',
    'drumclean': '筒清洁',
    'antibacterial': '除菌洗',
    'rinse_spin': '漂+脱',
    'spin': '单脱水',
    'quick': '快洗',
    'shirt': '衬衣',
    'jeans': '牛仔',
    'underwears': '内衣',
}

MIOT_STATES = [WASH_State.Unknown, WASH_State.Idle, WASH_State.Busy, WASH_State.Fault, WASH_State.Off]
STATE_NAMES = ['待机', '称重', '洗涤', '阶段3', '阶段4', '阶段5', '错误', '关机', '繁忙', '未知']
STATUS_PROPS = {PROP_Left_Time: '｜剩{}分钟', PROP_Dry_Mode: '｜烘干', PROP_Appoint_Time: '｜预约{}小时'}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    vol.Optional('did'): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    did = config.get('did')
    if host and token:
        add_entities([ZhiViomiWasher(name, did, Device(host, token))], True)
    elif did:
        add_entities([ZhiViomiCloudWasher(name, str(did))], True)
    else:
        _LOGGER.error('Need %s/%s or did.', CONF_HOST, CONF_TOKEN)


class ZhiViomiCloudWasher(ZhiPollEntity, VacuumEntity):

    def __init__(self, name, did):
        super().__init__(name, 'mdi:washing-machine')
        self.did = did
        self.values = [None for i in range(len(PROP_NAMES))]

    async def async_poll(self):
        await self.mi_poll()
        self._status = STATE_NAMES[self.values[PROP_Status]]
        if self.values[PROP_Paused]:
            self._status += '暂停'
        if self.is_on:
            self._status += ''.join([v.format(self.values[k]) for k, v in STATUS_PROPS.items() if self.values[k]])
        return True

    @property
    def device_state_attributes(self):
        return {list(PROP_NAMES.values())[i]: self.values[i] for i in range(len(self.values)) if self.values[i]}

    @property
    def supported_features(self):
        return SUPPORT_STATUS | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_FAN_SPEED | SUPPORT_START | SUPPORT_PAUSE | SUPPORT_STOP | SUPPORT_RETURN_HOME | SUPPORT_SEND_COMMAND

    @property
    def status(self):
        return self._status

    def update_status(self, status):
        self._status = status
        self.skip_update = True
        self.schedule_update_ha_state()

    @property
    def is_on(self):
        return self.values[PROP_Status] not in [WASH_State.Off, WASH_State.Unknown]

    async def async_turn_on(self, **kwargs):
        if self.values[PROP_Status] == WASH_State.Idle:
            self.update_status('已是待机状态')
        else:
            if self.values[PROP_Status] != WASH_State.Off:
                await self.async_stop()
                await sleep(1)
            if not await self.async_control('开机', PROP_Mode):
                self.values[PROP_Status] = WASH_State.Idle

    async def async_turn_off(self, **kwargs):
        await self.async_control('停止', -ACTION_Stop_Washing, WASH_State.Off)

    @property
    def fan_speed(self):
        return self.fan_speed_list[self.values[PROP_Mode] - 1]

    @property
    def fan_speed_list(self):
        return list(MODE_NAMES.values())

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        await self.async_control('设定' + fan_speed + '模式', PROP_Mode, self.fan_speed_list.index(fan_speed) + 1)

    @property
    def is_busy(self):
        status = self.values[PROP_Status]
        return status == WASH_State.Busy or (status >= WASH_State.Washing1 and self.values[PROP_Status] <= WASH_State.Washing6)

    async def async_start(self):
        if not self.values[PROP_Paused] and self.is_busy:
            lock = not self.values[PROP_Physical_Control_Locked]
            return await self.async_control('锁定' if lock else '解锁', PROP_Physical_Control_Locked, lock)
        if not self.is_on:
            await self.async_turn_on()
            await sleep(1)
        await self.async_control('启动', -ACTION_Start_Wash, WASH_State.Busy)

    async def async_pause(self):
        if self.is_busy:
            await self.async_control('暂停', -ACTION_Pause, WASH_State.Busy)
        else:
            self.update_status('非工作状态，无法暂停')

    async def async_stop(self, **kwargs):
        if self.values[PROP_Status] == WASH_State.Off:
            self.update_status('已经是关机状态')
        else:
            await self.async_turn_off()

    async def async_return_to_base(self, **kwargs):
        await self.async_stop()

    async def async_send_command(self, command, params=None, **kwargs):
        for item in command.split(';'):
            parts = item.split('=', 1)
            count = len(parts)
            cmd = parts[0]
            if count > 1:
                value = parts[1][1:] if parts[1].startswith('$') else int(parts[1])
            async_cmd = 'async_' + cmd
            if hasattr(self, async_cmd):
                # turn_on/turn_off,start/pause/stop/return_to_base,locate/clean_spot
                # fanspeed=$[value],dry_mode|appoint[=value]
                async_func = getattr(self, async_cmd)
                await (async_func(value) if count > 1 else async_func())
            elif count > 1:
                # program|water_temp|spin_level|DryMode|appoint_time=value
                piid = list(PROP_NAMES.keys()).index(cmd) if cmd in PROP_NAMES else int(cmd)
                code = await self.async_control('设定' + PROP_NAMES.get(cmd, ''), piid, value)
                if code is None:
                    continue
                elif code != 0:
                    return
            else:
                _LOGGER.error("Invalid speed format:%s", params)
                continue
            await sleep(1)

    async def async_control(self, doing, piid, value=None):
        if piid > 0:
            if value is None:
                value = self.values[piid]
            elif value == self.values[piid]:
                self.update_status('当前已' + doing)
                return None
        self.update_status('正在' + doing)
        code = await self.mi_control(piid, value)
        if code == 0:
            if piid > 0:
                self.values[piid] = value
            else:
                self.values[PROP_Status] = value
                self.values[PROP_Paused] = piid == -ACTION_Pause
                if piid == -ACTION_Stop_Washing:
                    self.values[PROP_Dry_Mode] = None
                    self.values[PROP_Appoint_Time] = None
            self.update_status(doing + '成功')
        else:
            self.update_status(doing + '错误：%s' % code)
        return code

    async def mi_poll(self):
        props = [(SRV_Physical_Control_Locked, PROP_Physical_Control_Locked)] + [(SRV_Washer, i) for i in range(PROP_Status, PROP_Spin_Speed + 1)]
        values = await miio_service.miot_get_props(self.did, props)
        for i in range(len(values)):
            self.values[i + 1] = MIOT_STATES[values[i]] if i + 1 == PROP_Status else values[i]

    async def mi_control(self, piid, value=None):
        if piid < 0:
            _LOGGER.debug('Cloud action: %s', -piid)
            return await miio_service.miot_do_action(self.did, SRV_Washer, -piid)
        _LOGGER.debug('Cloud set_prop: %s=%s', piid, value)
        siid = SRV_Physical_Control_Locked if piid == PROP_Physical_Control_Locked else SRV_Washer
        return await miio_service.miot_set_prop(self.did, siid, piid, value)


class ZhiViomiWasher(ZhiViomiCloudWasher):

    def __init__(self, name, did, device):
        super().__init__(name, did)
        self._device = device
        self._polls = 0

    @property
    def supported_features(self):
        return super().supported_features | SUPPORT_CLEAN_SPOT | SUPPORT_LOCATE

    async def async_clean_spot(self, **kwargs):
        if not self.is_on:
            await self.async_turn_on()
            await sleep(1)
        await self.async_dry_mode(0 if self.values[PROP_Dry_Mode] else 1)

    async def async_locate(self, **kwargs):
        if not self.is_on:
            await self.async_turn_on()
            await sleep(1)
        await self.async_appoint()

    async def async_dry_mode(self, mode=1):
        await self.async_control(('设定' if mode else '取消') + '烘干模式', PROP_Dry_Mode, DEFAULT_DRY_MODE if mode == 1 else mode)

    async def async_appoint(self, atime=DEFAULT_APPOINT_TIME):
        if atime < 0:
            aclock = -atime
            now = datetime.datetime.now()
            hour = now.hour
            if now.minute > 10:
                hour += 1
            if hour <= aclock - APPOINT_MIN:
                atime = aclock - hour
            elif hour >= aclock + 24 - APPOINT_MAX:
                atime = aclock + 24 - hour
            else:
                atime = 0
            status = '预约%s点钟完成洗衣' % aclock
        else:
            status = '预约%s小时后完成洗衣' % atime
        await (self.async_control(status, PROP_Appoint_Time, atime) if atime else super().async_start())

    async def mi_poll(self):
        self._polls += 1
        count = len(PROP_NAMES)
        if self.did and self._polls % (count + 1) != 2:
            try:
                #_LOGGER.debug('Cloud MiOT update')
                return await super().mi_poll()
            except Exception as e:
                _LOGGER.error("Cloud MiOT error: %s. Retry local MiIO.", e)

        cycle = self._polls % count
        keys = list(PROP_NAMES.keys())
        for i in range(count):
            if self.values[i] is not None and i != cycle:
                continue
            #_LOGGER.debug('Local MiIO update %s: %s', i, keys[i])
            value = await self.miio_send('get_prop', keys[i])
            if i == PROP_Mode:
                value = list(MODE_NAMES.keys()).index(value) + 1
            elif i == PROP_Paused:
                value = not value
            self.values[i] = value

    async def mi_control(self, piid, value=None):
        if piid < 0:
            name = 'set_wash_action'
            data = {ACTION_Start_Wash: 1, ACTION_Pause: 0, ACTION_Stop_Washing: 2}[-piid]
        elif piid == PROP_Mode:
            name = 'set_wash_program'
            data = list(MODE_NAMES.keys())[value - 1]
        else:
            data = value
            if piid == PROP_Physical_Control_Locked:
                name = 'set_child_lock'
            elif piid == PROP_Dry_Mode:
                name = 'SetDryMode'
            elif piid == PROP_Appoint_Time:
                name = 'set_appoint_time'
            else:
                name = piid
        _LOGGER.debug('Local action: %s=%s', name, data)
        try:
            ret = await self.miio_send(name, data)
            return 0 if ret == 'ok' else ret
        except Exception as e:
            _LOGGER.error("Error on local action: %s", e)
            return (await super().mi_control(piid, value)) if self.did else e

    async def miio_send(self, name, data):
        return (await self.hass.async_add_executor_job(self._device.send, name, [data]))[0]
