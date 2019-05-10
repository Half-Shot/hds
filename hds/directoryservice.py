import os
from os import path
import ssl
import logging
import base64
import asyncio
from .store import RedisStore
from .hosts import HostHandler
from .util import HDSFailure
# from .webinterface import WebInterface

from aiohttp import web
import aiohttp_cors


CERTPATH = path.realpath(path.join(path.curdir, os.environ.get("SSL_CERT", "cert.pem")))
KEYPATH = path.realpath(path.join(path.curdir, os.environ.get("SSL_KEY", "key.pem")))

PRIVKEY_PATH = os.environ.get("HDS_PRIVKEY_PATH")
PRIVKEY_DATA = os.environ.get("HDS_PRIVKEY_DATA")
PASSWORD = os.environ.get("HDS_PRIVKEY_PASSWORD")
HOST = os.environ.get("HDS_HTTP_HOST", "0.0.0.0")
NAME = os.environ.get("HDS_NAME", os.uname().nodename)

CONTACT_NAME = os.environ.get("HDS_CONTACT_NAME")
CONTACT_EMAIL = os.environ.get("HDS_CONTACT_EMAIL")
STATE_HOST = os.environ.get("HDS_HOST", "localhost")
REGISTER_HOSTS = os.environ.get("HDS_REGISTER_HOSTS", "").split(",")

PORT = int(os.environ.get("HDS_HTTP_PORT", "27012"))

logger = logging.getLogger(__name__)


class DirectoryService():
    @staticmethod
    async def __attach_headers(request, response: web.StreamResponse):
        response.headers["Server"] = "HostDiscoveryService/0.0.1"

    def __init__(self):
        self.store = RedisStore()
        if PRIVKEY_PATH is not None:
            self.hosthandler = HostHandler(self.store, key_path=PRIVKEY_PATH, password=PASSWORD)
        elif PRIVKEY_DATA is not None:
            self.hosthandler = HostHandler(self.store, key_data=base64.b64decode(PRIVKEY_DATA),
                                           password=PASSWORD)
        else:
            raise Exception("Private key not provided, cannot run")
        # self.webinterface = WebInterface(self.store, self.hosthandler)
        self.app = web.Application()
        # Configure default CORS settings.
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        })

        self.app.add_routes([
            web.get('/_hds/identify', self.get_version),
            web.get('/_hds/topics', self.get_topics),
            web.get('/_hds/topics/{topic}/{subtopics:.+}', self.get_topic),
            web.get('/_hds/topics/{topic}', self.get_topic),
            web.put('/_hds/hosts/{server}/state/{key}', self.put_state),
            web.get('/_hds/hosts/{server}', self.get_state),
            web.put('/_hds/hosts/{server}/topic/{topic}', self.put_topic),
            web.post('/_hds/register', self.post_register),
            # web.put('/_hds/federation/push', self.put_federation_topics),
        ])

        # self.webinterface.bind(self.app)

        # Configure CORS on all routes.
        for route in list(self.app.router.routes()):
            cors.add(route)

        self.app.on_response_prepare.append(DirectoryService.__attach_headers)

    async def start(self):
        logger.info("Started directory service")

        if path.exists(CERTPATH) and path.exists(KEYPATH):
            logger.debug("Cert: %s", CERTPATH)
            logger.debug("Key: %s", KEYPATH)
            sslcontext = sslf.create_default_context()
            sslcontext.check_hostname = False
            sslcontext.verify_mode = ssl.CERT_NONE
            sslcontext.load_cert_chain(CERTPATH, KEYPATH)
        else:
            logger.warn("Certpath or keypath not given or invalid, not using SSL")
            sslcontext = None
        my_name = self.hosthandler.fedClient.get_pubkey()
        self.hosthandler.put_state(
            my_name,
            "hds.host",
            self.hosthandler.fedClient.sign_payload({
                "hds.ttl": 60 * 60 * 24 * 3,
                "hds.host": STATE_HOST,
            })
        )

        self.hosthandler.put_state(
            my_name,
            "hds.name",
            self.hosthandler.fedClient.sign_payload({
                "hds.ttl": 60 * 60 * 24 * 3,
                "hds.name": NAME,
            })
        )

        if CONTACT_NAME:
            self.hosthandler.put_state(
                my_name,
                "hds.contact.name",
                self.hosthandler.fedClient.sign_payload({
                    "hds.ttl": 60 * 60 * 24 * 3,
                    "hds.contact.name": CONTACT_NAME,
                })
            )
        if CONTACT_EMAIL:
            self.hosthandler.put_state(
                my_name,
                "hds.contact.email",
                self.hosthandler.fedClient.sign_payload({
                    "hds.ttl": 60 * 60 * 24 * 3,
                    "hds.contact.email": CONTACT_EMAIL,
                })
            )
        # We need to register to a set of central hosts
        if "" in REGISTER_HOSTS:
            REGISTER_HOSTS.remove("")
        if len(REGISTER_HOSTS) > 0:
            # HACK: To allow the master process to start first.
            await asyncio.sleep(4)
        for host in REGISTER_HOSTS:
            logger.info("Registering with %s", host)
            await self.hosthandler.federation_register_with(host)
        logger.info("Registered with all hosts")

        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, HOST, PORT, ssl_context=sslcontext)
        await site.start()
        while True:
            await asyncio.sleep(1000)
        # wait for finish signal
        await runner.cleanup()

    async def get_version(self, request: web.Request):
        return web.json_response({
            "hds.servername": self.hosthandler.fedClient.get_pubkey(),
            "hds.type": "hds.directory"
        })

    async def get_body(self, request: web.Request):
        if request.content_type == "application/json":
            return await request.json()
        elif request.content_type is None:
            raise HDSFailure(
                "No Content-Type specified",
                type="hds.error.headers.missing"
            )
        else:
            raise HDSFailure(
                "Unsupported Content-Type",
                type="hds.error.headers.unsupported"
            )

    async def put_state(self, request: web.Request):
        server = request.match_info.get("server")
        key = request.match_info.get("key")
        try:
            body = await self.get_body(request)
            self.hosthandler.put_state(server, key, body)
        except HDSFailure as e:
            return web.json_response({
                "hds.error.text": str(e),
                "hds.error": e.type,
            }, status=400)
        return web.Response(status=201)

    async def get_state(self, request: web.Request):
        server = request.match_info.get("server")
        state = None
        try:
            state = self.store.get_host_state(server)
            if state is None:
                state = await self.hosthandler.find_via_federation(server)
        except HDSFailure as e:
            return web.json_response({
                "hds.error.text": str(e),
                "hds.error": e.type,
            }, status=400)
        if state is None:
            return web.json_response({
                "hds.error.text": "Host could not be found",
                "hds.error": "hds.error.host.missing",
            }, status=404)
        return web.json_response(
            state
        )

    async def get_topics(self, _):
        topics = self.store.get_topics()
        return web.json_response({
            "topics": topics,
        })

    async def get_topic(self, request: web.Request):
        hosts = self.store.get_topic_hosts(
            request.match_info.get("topic"),
            request.match_info.get("subtopics")
        )
        if hosts is None:
            return web.json_response({
                "hds.error.text": "Topic could not be found",
                "hds.error": "hds.error.topic.missing",
            }, status=404)
        return web.json_response({
            "hosts": hosts,
        })

    async def put_topic(self, request: web.Request):
        server = request.match_info.get("server")
        state = self.store.get_host_state(server)
        if state is None:
            return web.json_response({
                "hds.error.text": "Host could not be found",
                "hds.error": "hds.error.host.missing",
            }, status=404)
        if "hds.host" in state["hds.expired"]:
            return web.json_response({
                "hds.error.text": "hds.host has expired",
                "hds.error": "hds.error.host.expired",
            }, status=400)
        topic = request.match_info.get("topic")
        try:
            body = await self.get_body(request)
            await self.hosthandler.put_topic(server, topic, body)
        except HDSFailure as e:
            return web.json_response({
                "hds.error.text": str(e),
                "hds.error": e.type,
            }, status=400)
        return web.Response(status=201)

    async def post_register(self, request: web.Request):
        body = await self.get_body(request)
        try:
            self.hosthandler.federation_register_with(
                body.get("host")
            )
        except HDSFailure as e:
            return web.json_response({
                "hds.error.text": str(e),
                "hds.error": e.type,
            }, status=400)
        return web.Response(status=201)

    # async def put_federation_topics(self, request, web.Request):
        # body = await self.get_body(request)
        # try:
        #     self.hosthandler.put_host_topics(
        #         body.get("host")
        #     )
        # except HDSFailure as e:
        #     return web.json_response({
        #         "hds.error.text": str(e),
        #         "hds.error": e.type,
        #     }, status=400)
        # return web.Response(status=201)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(DirectoryService().start())
