from ..zhimi.entity import ZhiMIoTEntity
from .viomi_washer_v5 import *
from asyncio import sleep
from homeassistant.components.vacuum import SUPPORT_CLEAN_SPOT, SUPPORT_FAN_SPEED, SUPPORT_LOCATE, SUPPORT_PAUSE, SUPPORT_RETURN_HOME, SUPPORT_SEND_COMMAND, SUPPORT_START, SUPPORT_STATUS, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON, VacuumEntity
from homeassistant.const import CONF_HOST, CONF_TOKEN
import datetime
import homeassistant.helpers.config_validation as cv
import logging


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


PROP_KEYS = ['wash_status', 'child_lock', 'wash_process', 'program', 'remain_time', 'water_temp', 'spin_level', 'DryMode', 'appoint_time']

MODE_KEYS = [None, 'dry', 'weak_dry', 'refresh', 'goldenwash', 'super_quick', 'cottons', 'wool', 'down', 'drumclean', 'antibacterial', 'rinse_spin', 'spin', 'quick', 'shirt', 'jeans', 'underwears']
MODE_NAMES = ['黄金烘', '低温烘', '空气洗', '黄金洗', '超快洗', '棉织物', '羊毛', '羽绒服', '筒清洁', '除菌洗', '漂+脱', '单脱水', '快洗', '衬衣', '牛仔', '内衣']

MIOT_STATES = [WASH_State.Unknown, WASH_State.Idle, WASH_State.Busy, WASH_State.Fault, WASH_State.Off]
STATE_NAMES = ['待机', '称重', '洗涤', '阶段3', '阶段4', '阶段5', '错误', '关机', '繁忙', '未知']
STATUS_PROPS = {PROP_Paused: '｜暂停', PROP_Left_Time: '｜剩{}分钟', PROP_Dry_Mode: '｜烘干', PROP_Appoint_Time: '｜预约{}小时'}


class ZhiViomiCloudWasher(ZhiMIoTEntity, VacuumEntity):

    def __init__(self, conf):
        super().__init__(ALL_PROPS, conf, 'mdi:washing-machine')
        self.values = {PROP_Paused: None}

    async def async_poll(self):
        await self.mi_poll()
        self._status = STATE_NAMES[self.values[PROP_Status]]
        if self.is_on:
            self._status += ''.join([v.format(self.values[k]) for k, v in STATUS_PROPS.items() if self.values[k]])
        return self.values

    async def mi_poll(self):
        data = await super().async_poll()
        for k, v in data.items():
            self.values[k] = MIOT_STATES[v] if k == PROP_Status else v

    @property
    def supported_features(self):
        return SUPPORT_STATUS | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_FAN_SPEED | SUPPORT_START | SUPPORT_PAUSE | SUPPORT_STOP | SUPPORT_RETURN_HOME | SUPPORT_SEND_COMMAND

    @property
    def status(self):
        return self._status

    async def async_update_status(self, status):
        self._status = status
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self.values[PROP_Status] not in [WASH_State.Off, WASH_State.Unknown]

    async def async_turn_on(self, **kwargs):
        if self.values[PROP_Status] == WASH_State.Idle:
            await self.async_update_status('已是待机状态')
        else:
            if self.values[PROP_Status] != WASH_State.Off:
                await self.async_stop()
                await sleep(1)
            def success(siid, iid, value):
                self.values[PROP_Status] = WASH_State.Idle
            await self.async_control(SRV_Washer, PROP_Mode, None, '开机', success)

    async def async_turn_off(self, **kwargs):
        await self.async_action(ACTION_Stop_Washing, '停止')

    @property
    def fan_speed(self):
        return MODE_NAMES[self.values[PROP_Mode] - 1]

    @property
    def fan_speed_list(self):
        return MODE_NAMES

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        await self.async_control(SRV_Washer, PROP_Mode, self.fan_speed_list.index(fan_speed) + 1, '设定' + fan_speed + '模式')

    @property
    def is_busy(self):
        return self.values[PROP_Status] == WASH_State.Busy or (self.values[PROP_Status] >= WASH_State.Washing1 and self.values[PROP_Status] <= WASH_State.Fault)

    async def async_start(self):
        if not self.values[PROP_Paused] and self.is_busy:
            lock = not self.values[PROP_Physical_Control_Locked]
            return await self.async_control(SRV_Physical_Control_Locked, PROP_Physical_Control_Locked, lock, '锁定' if lock else '解锁')
        if not self.is_on:
            await self.async_turn_on()
            await sleep(1)
        await self.async_action(ACTION_Start_Wash, '启动')

    async def async_pause(self):
        if self.is_busy:
            await self.async_action(ACTION_Pause, '暂停')
        else:
            await self.async_update_status('非工作状态，无法暂停')

    async def async_stop(self, **kwargs):
        if self.values[PROP_Status] == WASH_State.Off:
            await self.async_update_status('已经是关机状态')
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
            elif count > 1 and cmd in PROP_KEYS:
                # program|water_temp|spin_level|DryMode|appoint_time=value
                piid = PROP_KEYS.index(cmd)
                code = await self.async_control(SRV_Washer, piid, value, '设定' + (ALL_PROPS[SRV_Washer].get(piid, '')))
                if code is None:
                    continue
                elif code != 0:
                    return
            else:
                _LOGGER.error("Invalid speed format:%s", params)
                continue
            await sleep(1)

    async def async_action(self, aiid, op):
        await self.async_control(SRV_Washer, aiid, [], op, self.action_success)

    def action_success(self, siid, aiid, value):
        self.values[PROP_Status] = (WASH_State.Busy, WASH_State.Off)[aiid == ACTION_Stop_Washing]
        self.values[PROP_Paused] = aiid == ACTION_Pause


class ZhiViomiWasher(ZhiViomiCloudWasher):

    def __init__(self, conf):
        super().__init__(conf)
        from miio import Device
        self._device = Device(conf[CONF_HOST], conf[CONF_TOKEN])
        self._polls = 0
        self.values[PROP_Dry_Mode] = None
        self.values[PROP_Appoint_Time] = None

    @property
    def supported_features(self):
        return super().supported_features | SUPPORT_CLEAN_SPOT | SUPPORT_LOCATE

    def action_success(self, siid, aiid, value):
        super().action_success(siid, aiid, value)
        if aiid == ACTION_Stop_Washing:
            self.values[PROP_Dry_Mode] = 0
            self.values[PROP_Appoint_Time] = 0

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
        await self.async_control(SRV_Washer, PROP_Dry_Mode, DEFAULT_DRY_MODE if mode == 1 else mode, ('设定' if mode else '取消') + '烘干模式')

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
        await (self.async_control(SRV_Washer, PROP_Appoint_Time, atime, status) if atime else super().async_start())

    async def mi_poll(self):
        self._polls += 1
        count = len(PROP_KEYS)
        if self.did and self._polls % (count + 1) != 2:
            try:
                #_LOGGER.debug('Cloud MiOT update')
                return await super().mi_poll()
            except Exception as e:
                _LOGGER.error("Cloud MiOT error: %s. Retry local MiIO.", e)

        cycle = self._polls % count
        for i in range(count):
            if self.values.get(i) is not None and i != cycle:
                continue
            #_LOGGER.debug('Local MiIO update %s: %s', i, PROP_KEYS[i])
            value = await self.miio_send('get_prop', PROP_KEYS[i])
            if i == PROP_Paused:
                self.values[PROP_Paused] = not value
            elif i == PROP_Mode:
                self.values[i] = MODE_KEYS.index(value)
            else:
                self.values[i] = value

    async def mi_control(self, siid, iid, value=[]):
        if isinstance(value, list):
            name = 'set_wash_action'
            data = {ACTION_Start_Wash: 1, ACTION_Pause: 0, ACTION_Stop_Washing: 2}[iid]
        elif iid == PROP_Mode:
            name = 'set_wash_program'
            data = MODE_KEYS[value]
        else:
            data = value
            if siid == PROP_Physical_Control_Locked:
                name = 'set_child_lock'
            elif iid == PROP_Dry_Mode:
                name = 'SetDryMode'
            elif iid == PROP_Appoint_Time:
                name = 'set_appoint_time'
            else:
                name = iid  # Impossible
        _LOGGER.debug('Local action: %s=%s', name, data)
        try:
            ret = await self.miio_send(name, data)
            return 0 if ret == 'ok' else ret
        except Exception as e:
            _LOGGER.error("Error on local action: %s", e)
            return (await super().mi_control(siid, iid, value)) if self.did else e

    async def miio_send(self, name, data):
        return (await self.hass.async_add_executor_job(self._device.send, name, [data]))[0]

