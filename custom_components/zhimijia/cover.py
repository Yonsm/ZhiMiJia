from ..zhi.cover import ZhiTravelCover
from ..zhimi.entity import ZhiMiEntity, ZHIMI_SCHEMA
from homeassistant.components.cover import PLATFORM_SCHEMA, STATE_CLOSED, STATE_OPEN, STATE_OPENING, STATE_CLOSING

AIRER_TRAVEL_TIME = 28

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(ZHIMI_SCHEMA)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([ZhiMrBondAirer(config)])


class ZhiMrBondAirer(ZhiMiEntity, ZhiTravelCover):

    def __init__(self, conf):
        ZhiTravelCover.__init__(self, AIRER_TRAVEL_TIME)
        ZhiMiEntity.__init__(self, ['dry', 'led', 'motor', 'drytime', 'airer_location'], conf, 'mdi:hanger')

    @property
    def available(self):
        return True

    async def async_poll(self):
        data = await super().async_poll()

        motor = int(data['airer_location'])
        if motor == 1:
            self._state = STATE_OPENING
        elif motor == 2:
            self._state = STATE_CLOSING

        location = int(data['airer_location'])
        if location == 1:
            self._position = 100
            self._state = STATE_OPEN
        elif location == 2:
            self._position = 0
            self._state = STATE_CLOSED
        elif self._state not in (STATE_OPENING, STATE_CLOSING):
            self._position = 50

        return data

    async def control_cover(self, op):
        return await self.async_control('motor', [1, 2, 0][op])
