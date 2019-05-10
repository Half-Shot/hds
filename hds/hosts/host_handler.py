import logging
from os import path
from ..util import verify_payload, HDSFailure, determine_our_host
from ..client import DirectoryClient
logger = logging.getLogger(__name__)

MAX_TTL_SEC = 60 * 60 * 24 * 3
MIN_TTL_SEC = 60 * 60 * 1
MAX_KEY_SIZE = 1024
MAX_VALUE_SIZE = 1024 * 64


class HostHandler():
    def __init__(self, store, key_path=None, key_data=None, password=None):
        self.store = store
        try:
            if key_path is not None:
                key_path = path.realpath(path.join(path.curdir, key_path))
                self.fedClient = DirectoryClient(private_key_path=key_path, password=password)
            elif key_data is not None:
                self.fedClient = DirectoryClient(private_key_data=key_data, password=password)
            else:
                raise FileNotFoundError("No key file provided")
        except FileNotFoundError as e:
            logger.error("You have not provided a HDS_PRIVKEY_PATH envvar," +
                         "so this directory will not be able to federate: %s", e)
            self.fedClient = None

    def __parseStatePayload(self, body, contentType):
        pass

    def __validate_host(self, b64serverKey, host):
        # Determine whether the given host is the same as the requestor by sending it a
        # random string and expecting a response back with the same signature.
        # TODO: This
        logger.warning("__validate_host: Skipping validation!")
        return True

    def find_via_federation(self, b58_server_key):
        if self.fedClient is None:
            raise HDSFailure("Federation on this host is disabled",
                             type="hds.error.federation.disabled")
        # Get hosts like us, ensure paranoid mode is set to avoid hijacks.
        hosts = self.store.get_topic_hosts("hds.directory")
        if hosts is None:
            raise HDSFailure("No hds.directory hosts have been registered",
                             type="hds.error.federation.no_hosts")
        for srvkey in hosts.keys():
            logger.info("Asking %s.. for information on %s.." % srvkey[:16], b58_server_key[:16])
            # state = self.fedClient.get_state(b58_server_key, state["hds.host"])
            # TODO: Finish this.

    async def federate_topic(self, b58_server_key, topic, body):
        dir_hosts = self.store.get_topic_hosts("hds.directory")
        topic_owner_state = self.store.get_host_state(b58_server_key)
        for host in dir_hosts:
            logger.info("Federating new topic to %s", host)
            state = self.store.get_host_state(host)
            if "hds.type" in state["hds.expired"] or "hds.host" in state["hds.expired"]\
                    or "hds.directory.url" not in state:
                logger.warn("hds.type or hds.host has expired for host, not federating")
                continue
            host_addr = state["hds.directory.url"]["value"]
            host_state = topic_owner_state["hds.host"]
            try:
                # Ensure that the hds.host state is federated first.
                await self.fedClient.send_state_payload("hds.host", {
                    "hds.ttl": host_state["hds.ttl"],
                    "hds.host": host_state["value"],
                    "hds.signature": host_state["hds.signature"],
                }, b58_server_key, host_addr)
                await self.fedClient.put_topic_payload(topic, body, b58_server_key, host_addr)
            except Exception as e:
                logger.warn("Failed to federate to %s (%s): %s", host, host_addr, str(e))

    async def federation_register_with(self, host):
        if self.fedClient is None:
            raise HDSFailure("Federation on this host is disabled",
                             type="hds.error.federation.disabled")
        await self.fedClient.send_state("hds.host", determine_our_host(),
                                        baseurl=host, ttl=MAX_TTL_SEC)
        await self.fedClient.send_state("hds.type", "hds.directory",
                                        baseurl=host, ttl=MAX_TTL_SEC)
        # Hackaround to set url of directory
        await self.fedClient.send_state("hds.directory.url", "http://" + determine_our_host() + ":27012",
                                        baseurl=host, ttl=MAX_TTL_SEC)
        await self.fedClient.put_topic("hds.directory", baseurl=host)

    async def put_topic(self, b58_server_key, topic, body):
        log_id = b58_server_key[:12]
        logger.info("[%s] Request to set topic %s ", log_id, topic)
        if len(topic) > MAX_KEY_SIZE:
            raise HDSFailure("Topic too long",
                             type="hds.error.payload.key_too_long")
        if len(topic) < 3:
            raise HDSFailure("Topic too short",
                             type="hds.error.payload.key_too_short")
        subtopics = body.get(topic, [])
        if not isinstance(subtopics, list):
            raise HDSFailure("subtopics is the wrong type", type="hds.error.payload.bad_type")
        sig = body["hds.signature"]
        verify_payload(b58_server_key, body)
        logger.info("[%s] Request verified, storing topic", log_id)
        self.store.store_host_topic(server=b58_server_key, topic=topic,
                                    subtopics=subtopics, signature=sig)
        body["hds.signature"] = sig
        await self.federate_topic(b58_server_key, topic, body)

    def put_state(self, b58_server_key: str, key, body):
        log_id = b58_server_key[:12]
        logger.info("[%s] Request to set %s = %s ", log_id, key, body.get(key)[:32])
        if len(key) > MAX_KEY_SIZE:
            raise HDSFailure("State key too long",
                             type="hds.error.payload.key_too_long")
        if len(key) < 3:
            raise HDSFailure("State key too short",
                             type="hds.error.payload.key_too_short")
        if body.get(key) is None:
            raise HDSFailure("Missing {} from payload".format(key),
                             type="hds.error.payload.missing_key")
        if not isinstance(body.get(key), str):
            raise HDSFailure("{} is not a string".format(key),
                             type="hds.error.payload.bad_type")
        if len(body.get(key)) < 1:
            raise HDSFailure("State body too short",
                             type="hds.error.payload.body_too_short")
        if len(body.get(key)) > MAX_VALUE_SIZE:
            raise HDSFailure("State body too long",
                             type="hds.error.payload.body_too_long")

        sig = body.get("hds.signature")
        if sig is None:
            raise HDSFailure("Missing hds.signature from payload",
                             type="hds.error.payload.missing_key")
        ttl = body.get("hds.ttl")
        if ttl is None:
            raise HDSFailure("Missing hds.ttl from payload", type="hds.error.payload.missing_key")
        if isinstance(ttl, str):
            raise HDSFailure("hds.ttl must be a number", type="hds.error.payload.bad_ttl")
        if MAX_TTL_SEC < ttl < MIN_TTL_SEC:
            raise HDSFailure("TTL cannot be higher than {} or lower than {}".format(
                MAX_TTL_SEC, MIN_TTL_SEC), type="hds.error.payload.bad_ttl"
            )

        sig = body["hds.signature"]
        verify_payload(b58_server_key, body)

        # # Check to see if the host exists or has expired.
        try:
            host = self.store.get_host_state(b58_server_key)
        except HDSFailure:
            host = None
        # TODO: What about hds.status
        # Check to see if they have provided a `hds.host` or a `hds.status`
        if host is None or "hds.host" in host["hds.expired"]:
            host = body.get("hds.host")
            if host is None:
                raise HDSFailure(
                    "The hds.host entry has expired, but you have not provided a new value",
                    "hds.error.state.no_host"
                )
        # Invoke host verification if needed.
        if body.get("hds.host"):
            self.__validate_host(b58_server_key, host)

        logger.info("[%s] Request verified, storing state", log_id)

        self.store.store_host_state(
            server=b58_server_key, key=key, value=body.get(key), ttl=ttl, signature=sig
        )
        # TODO: Figure out how we alert the federation to changes
