from homeassistant.util import slugify

import logging

_LOGGER = logging.getLogger(__name__)


class ZhiEntity:

    def __init__(self, name, icon):
        self._name = name
        self._icon = icon

    @property
    def unique_id(self):
        return self.__class__.__name__.lower() + slugify(self._name)

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon


class ZhiPollEntity(ZhiEntity):

    data = None
    skip_poll = False

    @property
    def available(self):
        return self.data is not None

    @property
    def should_poll(self):
        if self.skip_poll:
            self.skip_poll = False
            return False
        return True

    async def async_update(self):
        try:
            self.data = await self.async_poll()
        except Exception as e:
            _LOGGER.error("Error on update: %s", e)
            self.data = None

    async def async_poll(self):
        return await self.hass.async_add_executor_job(self.poll)

    def poll(self):
        raise None
