from ..zhimi.entity import ZhiMIoTEntity
from .viomi_washer_v13 import *
from asyncio import sleep
from homeassistant.components.vacuum import SUPPORT_CLEAN_SPOT, SUPPORT_FAN_SPEED, SUPPORT_LOCATE, SUPPORT_PAUSE, SUPPORT_RETURN_HOME, SUPPORT_SEND_COMMAND, SUPPORT_START, SUPPORT_STATUS, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON, VacuumEntity
from homeassistant.const import CONF_HOST, CONF_TOKEN
from datetime import datetime, timedelta
import logging


_LOGGER = logging.getLogger(__name__)

APPOINT_MIN = 1  # 3 in app default
APPOINT_MAX = 23  # 19 in app default
DEFAULT_APPOINT_TIME = -8  # -8 means 8 o'clock, 8 means 8 hours later


PROP_IIDS = {
    'switch_status': PROP_Switch_Status,
    'mode': PROP_Mode,
    'target_temperature': PROP_Target_Temperature,
    'spin_speed': PROP_Spin_Speed,
    'drying_time': PROP_Drying_Time,
    'rinsh_times': PROP_Rinsh_Times,
    'speed_level': PROP_Speed_Level,
}


class ZhiViomiCloudWasher(ZhiMIoTEntity, VacuumEntity):

    def __init__(self, conf):
        super().__init__(ALL_PROPS, conf, 'mdi:washing-machine')
        self.values = {}

    async def async_poll(self):
        await self.mi_poll()
        self._status = VALUE_Status(self.values[PROP_Status]).name
        if self.values[PROP_Status] == VALUE_Status.暂停:
            self._status += '｜暂停'
        if self.values[PROP_Status] != VALUE_Status.关机:
            left_time = self.values[PROP_Left_Time]
            if left_time:
                self._status += '｜剩%s分钟' % left_time
            drying_time = self.values[PROP_Drying_Time]
            if drying_time:
                self._status += '|' + VALUE_Drying_Time(drying_time).name
            appoint_time = self.values[PROP_预约完成时间]
            if appoint_time:
                self._status += '｜预约%s' % datetime.fromtimestamp(appoint_time).strftime('%H:%M')
        return self.values

    async def mi_poll(self):
        data = await super().async_poll()
        for k, v in data.items():
            self.values[k] = v

    @property
    def supported_features(self):
        return SUPPORT_STATUS | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_FAN_SPEED | SUPPORT_START | SUPPORT_PAUSE | SUPPORT_STOP | SUPPORT_RETURN_HOME | SUPPORT_SEND_COMMAND | SUPPORT_CLEAN_SPOT | SUPPORT_LOCATE

    @property
    def status(self):
        return self._status

    async def async_update_status(self, status):
        self._status = status
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self.values[PROP_Status] != VALUE_Status.关机

    async def async_turn_on(self, **kwargs):
        if self.values[PROP_Status] == VALUE_Status.待机:
            await self.async_update_status('已是待机状态')
        else:
            if self.values[PROP_Status] != VALUE_Status.关机:
                await self.async_turn_off()
                await sleep(1)

            def success(siid, iid, value):
                self.values[PROP_Status] = VALUE_Status.待机
            await self.async_control(SRV_Washer, PROP_Switch_Status, True, '开机', success, True)

    async def async_turn_off(self, **kwargs):
        def success(siid, iid, value):
            self.values[PROP_Status] = VALUE_Status.关机
        await self.async_control(SRV_Washer, PROP_Switch_Status, False, '关机', success, True)

    @property
    def fan_speed(self):
        return VALUE_Mode(self.values[PROP_Mode]).name

    @property
    def fan_speed_list(self):
        return [e.name for e in VALUE_Mode]

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        await self.async_control(SRV_Washer, PROP_Mode, self.fan_speed_list.index(fan_speed) + 1, '设定' + fan_speed + '模式')

    async def async_start(self):
        if self.values[PROP_Status] == VALUE_Status.繁忙:
            lock = not self.values[PROP_Physical_Control_Locked]
            return await self.async_control(SRV_Physical_Control_Locked, PROP_Physical_Control_Locked, lock, '锁定' if lock else '解锁')
        if not self.is_on:
            await self.async_turn_on()
            await sleep(1)
        await self.async_action(ACTION_Start_Wash, '启动')

    async def async_pause(self):
        if self.values[PROP_Status] == VALUE_Status.繁忙:
            await self.async_action(ACTION_Pause, '暂停')
        else:
            await self.async_update_status('非工作状态，无法暂停')

    async def async_stop(self, **kwargs):
        if self.values[PROP_Status] == VALUE_Status.关机:
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
            elif count > 1 and cmd in PROP_IIDS:
                piid = PROP_IIDS[cmd]
                code = await self.async_control(SRV_Washer, piid, value, '设定' + (ALL_PROPS[SRV_Washer].get(piid, '')))
                if code is None:
                    continue
                elif code == False:
                    return
            else:
                _LOGGER.error("Invalid speed format:%s", params)
                continue
            await sleep(1)

    async def async_action(self, aiid, op):
        await self.async_control(SRV_Washer, aiid, [self.values[PROP_Mode]], op, self.action_success)

    def action_success(self, siid, aiid, value):
        self.values[PROP_Status] = (VALUE_Status.繁忙, VALUE_Status.暂停)[aiid == ACTION_Start_Wash]

    async def async_clean_spot(self, **kwargs):
        if not self.is_on:
            await self.async_turn_on()
            await sleep(1)
        await self.async_dry_mode(0 if self.values[PROP_Drying_Time] else 1)

    async def async_locate(self, **kwargs):
        if not self.is_on:
            await self.async_turn_on()
            await sleep(1)
        await self.async_appoint()

    async def async_dry_mode(self, mode=1):
        await self.async_control(SRV_Washer, PROP_Drying_Time, VALUE_Drying_Time.智能烘干 if mode == 1 else mode, ('设定' if mode else '取消') + '烘干模式')

    async def async_appoint(self, atime=DEFAULT_APPOINT_TIME):
        now = datetime.now()
        if atime < 0:
            aclock = -atime
            if now.hour > aclock:
                now += timedelta(days=1)
            status = '预约%s点钟完成洗衣' % aclock
            stamp = datetime(now.year, now.month, now.day, aclock).timestamp()
        else:
            status = '预约%s小时后完成洗衣' % atime
            stamp = now.timestamp() + atime * 60 * 60 * 1000
        await (self.async_control(SRV_自定义属性, PROP_预约完成时间, int(stamp), status) if atime else self.async_start())


class ZhiViomiWasher(ZhiViomiCloudWasher):
    pass
