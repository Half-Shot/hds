import os
from ..store import Store
from ..hosts import HostHandler
from aiohttp import web

NAME = os.environ.get("HDS_NAME", "HDS Instance")


class WebInterface:
    def __init__(self, store: Store, host: HostHandler):
        self.store = store
        self.host = host
        pass

    def bind(self, app: web.Application):
        app.router.add_static('/static/',
                              path='./hds/webinterface/static/',
                              name='webinterface',
                              show_index=True)
        app.router.add_get("/webinterface/stats", self.get_stats)
        pass

    def get_stats(self, req: web.Request):
        return web.json_response({
            "name": NAME,
            "servername": self.host.fedClient.get_pubkey(),
            "nodes": [],
            "topics:": [],
        })
