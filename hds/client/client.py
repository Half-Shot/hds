import logging
import base64
import base58
from aiohttp import ClientSession, ClientResponse
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from canonicaljson import encode_canonical_json
from ..util import HDSFailure, HDSBadKeyFailure, verify_payload

load_pem_private_key = serialization.load_pem_private_key

logger = logging.getLogger(__name__)

ONE_DAY = 60 * 60 * 24
SSL_ENABLED = False


class DirectoryClient:
    HDS_HOST = "hds.host"
    mock_session = None

    def __get_session(self):  # pragma: no cover
        if self.mock_session is not None:
            return self.mock_session
        return ClientSession()

    @staticmethod
    def check_error(res):
        if res.get("hds.error", False):
            raise HDSFailure(res["hds.error.text"], res["hds.error"])

    @staticmethod
    def format_baseurl(url):
        return (url if url.startswith("http") else "https://" + url) + "/_hds"

    def __init__(self, base_url: str = None, private_key_path=None,
                 private_key_data=None,
                 password=None, paranoid_mode=True):
        self.paranoid_mode = paranoid_mode
        self.base_url = base_url
        if private_key_path is not None:
            with open(private_key_path, "rb") as f:
                private_key_data = f.read()
        elif private_key_data is None:
            self.pub_key = None
            self.key = None
            return

        try:
            self.key: rsa.RSAPrivateKey = load_pem_private_key(
                private_key_data,
                password=password,
                backend=default_backend()
            )
            if not isinstance(self.key, rsa.RSAPrivateKey):
                raise TypeError("Private key is wrong type, expected public key")
        except Exception as ex:
            raise HDSBadKeyFailure("Failed to read key", inner_ex=ex)

        self.pub_key = base58.b58encode(self.key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )).decode()

    def get_pubkey(self):
        if self.pub_key is None:
            raise HDSBadKeyFailure("Client was not initialised with a key")
        return self.pub_key

    def sign_payload(self, payload):
        if self.pub_key is None:
            raise HDSBadKeyFailure("Client was not initialised with a key, cannot sign payload")
        if len(payload.keys()) < 1:
            raise HDSFailure(
                "No keys were given in the payload, cannot sign payload.",
                "hds.payload.empty")
        signature = self.key.sign(
            encode_canonical_json(payload),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA512()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA512()
        )
        payload["hds.signature"] = base64.b64encode(signature).decode()
        logger.debug("sign_payload %s", str(payload))
        return payload

    async def send_state(self, key, value, ttl=ONE_DAY, baseurl=None):
        if ttl < 10:
            raise ValueError("TTL was < 10")
        payload = self.sign_payload({"hds.ttl": ttl, key: value})
        await self.send_state_payload(key, payload, self.pub_key, baseurl)

    async def send_state_payload(self, key, payload, pub_key, baseurl=None):
        baseurl = DirectoryClient.format_baseurl(baseurl if baseurl is not None else self.base_url)
        async with self.__get_session() as session:
            url = "{}/hosts/{}/state/{}".format(baseurl, pub_key, key)
            res = await session.put(url=url, json=payload, ssl=SSL_ENABLED)
            if res.status == 201:
                return
            DirectoryClient.check_error(await res.json())

    async def put_topic(self, topic, subtopics=[], baseurl=None):
        payload = self.sign_payload({topic: subtopics})
        await self.put_topic_payload(topic, payload, self.pub_key, baseurl)

    async def put_topic_payload(self, topic, payload, pub_key, baseurl=None):
        baseurl = DirectoryClient.format_baseurl(baseurl if baseurl is not None else self.base_url)
        async with self.__get_session() as session:
            url = "{}/hosts/{}/topic/{}".format(baseurl, pub_key, topic)
            res = await session.put(url=url, json=payload, ssl=SSL_ENABLED)
            if res.status == 201:
                return
            DirectoryClient.check_error(await res.json())

    async def get_topic(self, topic: str, subtopics=[], baseurl=None):
        baseurl = DirectoryClient.format_baseurl(baseurl if baseurl is not None else self.base_url)
        if type(topic) is not str or len(topic) < 1:
            raise ValueError("Topic should be a non-empty string")
        async with self.__get_session() as session:
            url = "{}/topics/{}".format(baseurl, topic)
            if len(subtopics) > 0:
                url += "/" + "/".join(subtopics)
            res = await session.get(url=url, ssl=False)
            j = await res.json()
            DirectoryClient.check_error(j)
            return j

    async def get_host_topic(self, server: str, topic: str, baseurl=None):
        baseurl = DirectoryClient.format_baseurl(baseurl if baseurl is not None else self.base_url)
        if type(topic) is not str or len(topic) < 1:
            raise ValueError("Topic should be a non-empty string")
        async with self.__get_session() as session:
            url = "{}/hosts/{}/topic/{}".format(baseurl, server, topic)
            res = await session.get(url=url, ssl=False)
            j = await res.json()
            print(j)
            DirectoryClient.check_error(j)
            return j


    async def get_topics(self, baseurl=None):
        baseurl = DirectoryClient.format_baseurl(baseurl if baseurl is not None else self.base_url)
        async with self.__get_session() as session:
            url = "{}/topics".format(baseurl)
            res = await session.get(url=url, ssl=False)
            j = await res.json()
            DirectoryClient.check_error(j)
            return j["topics"]

    async def get_state(self, servername: str, baseurl=None, raw=False):
        short_name = servername[:16]
        baseurl = DirectoryClient.format_baseurl(baseurl if baseurl is not None else self.base_url)
        async with self.__get_session() as session:
            url = "{}/hosts/{}".format(baseurl, servername)
            res: ClientResponse = await session.get(url=url, ssl=SSL_ENABLED)
            DirectoryClient.check_error(await res.json())
            body: dict = await res.json()
            if raw:
                return body
            expired = body.pop("hds.expired", [])
            if self.paranoid_mode:
                for key in expired:
                    logging.warning("key %s has expired" % key)
                    body.pop(key)
            state = {}
            logging.debug("Verifying keys from %s", short_name)
            for key in body.keys():
                item = body.get(key)
                sig = item["hds.signature"]
                if sig is None:
                    logging.warning("%s has no signature", key)
                    continue
                verify_payload(b58_server_key=servername, body={
                    key: item.get("value"),
                    "hds.signature": item.get("hds.signature"),
                    "hds.ttl": item.get("hds.ttl"),
                })
                state[key] = item.get("value")
            return state

    async def identify(self, baseurl=None):
        baseurl = DirectoryClient.format_baseurl(
            baseurl if baseurl is not None else self.base_url)
        async with self.__get_session() as session:
            url = "{}/identify".format(baseurl)
            res: ClientResponse = await session.get(url=url, ssl=SSL_ENABLED)
            j = await res.json()
            DirectoryClient.check_error(j)
            return j
