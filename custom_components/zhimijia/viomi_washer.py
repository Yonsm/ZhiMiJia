from ..zhimi.entity import ZhiMiEntity
from asyncio import sleep
from homeassistant.components.vacuum import SUPPORT_CLEAN_SPOT, SUPPORT_FAN_SPEED, SUPPORT_LOCATE, SUPPORT_PAUSE, SUPPORT_RETURN_HOME, SUPPORT_SEND_COMMAND, SUPPORT_START, SUPPORT_STATUS, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON, StateVacuumEntity
from datetime import datetime, timedelta
import logging


_LOGGER = logging.getLogger(__name__)

APPOINT_MIN = 1  # 3 in app default
APPOINT_MAX = 23  # 19 in app default
DEFAULT_APPOINT_TIME = -8  # -8 means 8 o'clock, 8 means 8 hours later


class ZhiMiVacuum(ZhiMiEntity, StateVacuumEntity):

    def __init__(self, hass, conf, model):
        from importlib import import_module
        module = import_module('.' + model.replace('.', '_'), __package__)
        for x in module.__dict__:
            if not x.startswith('_') and x != 'Enum':
                setattr(self, x, getattr(module, x))
        super().__init__(hass, self.ALL_SVCS, conf, 'mdi:washing-machine')
        self.model = model

    async def async_poll(self):
        data = await super().async_poll()
        self._attr_state = self.Washer_Status(data[self.Washer.Status]).name
        if data[self.Washer.Status] == self.Washer_Status.暂停:
            self._attr_state += '｜暂停'
        if data[self.Washer.Status] != self.Washer_Status.docked:
            left_time = data[self.Washer.Left_Time]
            if left_time:
                self._attr_state += '｜剩%s分钟' % left_time
            drying_time = data[self.Washer.Drying_Time]
            if drying_time:
                self._attr_state += '|' + \
                    self.Washer_Drying_Time(drying_time).name
            appoint_time = data[self.Custom.Appoint_Time]
            if appoint_time:
                self._attr_state += '｜预约%s' % datetime.fromtimestamp(
                    appoint_time).strftime('%H:%M')
        return data

    @property
    def supported_features(self):
        return SUPPORT_STATUS | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_FAN_SPEED | SUPPORT_START | SUPPORT_PAUSE | SUPPORT_STOP | SUPPORT_RETURN_HOME | SUPPORT_SEND_COMMAND | SUPPORT_CLEAN_SPOT | SUPPORT_LOCATE

    async def async_update_status(self, status):
        self._attr_state = status
        await super().async_update_status(status)

    @property
    def is_on(self):
        return self.data[self.Washer.Status] != self.Washer_Status.docked

    async def async_turn_on(self, **kwargs):
        if self.data[self.Washer.Status] == self.Washer_Status.待机:
            await self.async_update_status('已是待机状态')
        else:
            if self.data[self.Washer.Status] != self.Washer_Status.docked:
                await self.async_turn_off()
                await sleep(1)

            def success(iid, value):
                self.data[self.Washer.Status] = self.Washer_Status.待机
                self._attr_state = '待机'
                self.async_write_ha_state()
            await self.async_control(self.Washer.Switch_Status, True, '开机', success, True)

    async def async_turn_off(self, **kwargs):
        def success(iid, value):
            self.data[self.Washer.Status] = self.Washer_Status.docked
            self._attr_state = 'docked'
            self.async_write_ha_state()
        await self.async_control(self.Washer.Switch_Status, False, '关机', success, True)

    @property
    def fan_speed(self):
        return self.Washer_Mode(self.data[self.Washer.Mode]).name

    @property
    def fan_speed_list(self):
        return [e.name for e in self.Washer_Mode]

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        await self.async_control(self.Washer.Mode, self.fan_speed_list.index(fan_speed) + 1, '设定' + fan_speed + '模式')

    async def async_start(self):
        if self.data[self.Washer.Status] == self.Washer_Status.繁忙:
            lock = not self.data[self.Physical_Control_Locked.Physical_Control_Locked]
            return await self.async_control(self.Physical_Control_Locked.Physical_Control_Locked, lock, '锁定' if lock else '解锁')
        if not self.is_on:
            await self.async_turn_on()
            await sleep(1)
        await self.async_control(self.Washer._Start_Wash, [self.data[self.Washer.Mode]], '启动', self.action_success)

    async def async_pause(self):
        if self.data[self.Washer.Status] == self.Washer_Status.繁忙:
            await self.async_control(self.Washer._Pause, [self.data[self.Washer.Mode]], '暂停', self.action_success)
        else:
            await self.async_update_status('非工作状态，无法暂停')

    def action_success(self, iid, value):
        self.data[self.Washer.Status] = (self.Washer_Status.繁忙, self.Washer_Status.暂停)[
            iid == self.Washer._Start_Wash]

    async def async_stop(self, **kwargs):
        if self.data[self.Washer.Status] == self.Washer_Status.docked:
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
                value = parts[1][1:] if parts[1].startswith(
                    '$') else int(parts[1])
            async_cmd = 'async_' + cmd
            if hasattr(self, async_cmd):
                # turn_on/turn_off,start/pause/stop/return_to_base,locate/clean_spot
                # fanspeed=$[value],dry_mode|appoint[=value]
                async_func = getattr(self, async_cmd)
                await (async_func(value) if count > 1 else async_func())
            elif count > 1 and cmd in self.attrs:
                prop = self.props[self.attrs.index(cmd)]
                code = await self.async_control(prop, value, '设定' + cmd)
                if code is None:
                    continue
                elif code == False:
                    return
            elif cmd != 'sleep':
                _LOGGER.error("Invalid item: %s", item)
            await sleep(1)

    async def async_clean_spot(self, **kwargs):
        if not self.is_on:
            await self.async_turn_on()
            await sleep(1)
        await self.async_dry_mode(0 if self.data[self.Washer.Drying_Time] else 1)

    async def async_locate(self, **kwargs):
        if not self.is_on:
            await self.async_turn_on()
            await sleep(1)
        await self.async_appoint()

    async def async_dry_mode(self, mode=1):
        await self.async_control(self.Washer.Drying_Time, self.Washer_Drying_Time.智能烘干 if mode == 1 else mode, ('设定' if mode else '取消') + '烘干模式')

    async def async_appoint(self, atime=DEFAULT_APPOINT_TIME):
        now = datetime.now()
        now_stamp = now.timestamp()
        if atime < 0:
            aclock = -atime
            status = '预约%s点钟完成洗衣' % aclock
            hour = now.hour
            if self.model == 'viomi.washer.v13':
                if hour > aclock:
                    now += timedelta(days=1)
                stamp = datetime(now.year, now.month,
                                 now.day, aclock).timestamp()
                if (stamp - now_stamp) / 3600 > 12:
                    atime = 0
            else:
                if now.minute > 10:
                    hour += 1
                if hour <= aclock - APPOINT_MIN:
                    stamp = aclock - hour
                elif hour >= aclock + 24 - APPOINT_MAX:
                    stamp = aclock + 24 - hour
                else:
                    stamp = 0
                if stamp > 12:
                    atime = 0
        else:
            status = '预约%s小时后完成洗衣' % atime
            stamp = (now_stamp + atime * 60 * 60 *
                     1000) if self.model == 'viomi.washer.v13' else atime
        await (self.async_control(self.Custom.Appoint_Time, int(stamp), status) if atime else self.async_start())
