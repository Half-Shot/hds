import unittest
import asyncio
from hds.client import DirectoryClient
from hds.util import HDSBadKeyFailure, HDSFailure, verify_payload
from spec.mocks.directoryservicemock import MockClientSession

GOOD_PUB_KEY = "2TuPVgMCHJy5atawrsADEzjP7MCVbyyCA89UW6Wvjp9HrC1rUKkbd"
GOOD_PUB_KEY += "UxorDbJLtH5TsmXW7Ey6FxARzJCWmKdubWceoFEyrmWXVjKAMR176"
GOOD_PUB_KEY += "JGXkpKQavsNhtszu3AZHB2aW1ZqWq9DxAWxzyzwxAchwbXRQ5kNkU"
GOOD_PUB_KEY += "sz7VFygC5LJ8hLGrzRAzBiY1SN7EKnA8v7Nj5cNvX4DFwYhAYegf1"
GOOD_PUB_KEY += "VSa2SMFrmH1sy8m8VkrRsRojTst84qE4dt5qhMroeNXyfDfgzd6pe"
GOOD_PUB_KEY += "WXjuVjjkLqGv7sbhJxqLzGJb5gX12eZ9TNMfGBA2B3gw6j8ZLVAwt"
GOOD_PUB_KEY += "iuGAnaybBWUh9WyJT2JCRKVcJsaoyChvChauRwXWyQEb72eKDf4z8"
GOOD_PUB_KEY += "VmSjB71gEpx5mmdZ4oHnCmNWLE3w5sn"


class ClientTestCase(unittest.TestCase):

    def gen_client(self, opts={}, paranoid_mode=True):
        c = DirectoryClient("http://localhost:11111", private_key_path="spec/unit/privkey.pem", paranoid_mode=paranoid_mode)
        if opts.get("state") == None:
            c.mock_session = MockClientSession(opts)
            return c
        serversState = {}
        for srvname, state in opts.get("state").items():
            srvState = {}
            for k, v in state.items():
                if k == "hds.expired":
                    srvState["hds.expired"] = v
                    continue
                srvState[k] = c.sign_payload({k: v, "hds.ttl": 60000})
                val = srvState[k][k]
                srvState[k]["value"] = val
                del srvState[k][k]
            serversState[srvname] = srvState
        c.mock_session = MockClientSession(opts, serversState)
        return c

    def setUp(self):
        pass

    def tearDown(self):
        pass

    # Key-less tests

    def test_init_no_key(self):
        client = DirectoryClient("http://localhost:11111", paranoid_mode=False)
        self.assertEqual(client.base_url, "http://localhost:11111")
        self.assertEqual(client.paranoid_mode, False)
        self.assertIsNone(client.pub_key)
        self.assertIsNone(client.key)

    def test_get_pubkey_nokey(self):
        client = DirectoryClient("http://localhost:11111")
        with self.assertRaises(HDSBadKeyFailure):
            client.get_pubkey()

    def test_sign_payload_nokey(self):
        client = DirectoryClient("http://localhost:11111")
        with self.assertRaises(HDSBadKeyFailure):
            client.sign_payload({"some": "payload"})

    def test_init_bad_key(self):
        with self.assertRaises(HDSBadKeyFailure):
            DirectoryClient("http://localhost:11111", private_key_path="spec/unit/badkey.pem")

    # Tests using a priv key

    def test_init_key(self):
        client = self.gen_client()
        self.assertIsNotNone(client.key)
        self.assertEqual(client.pub_key, GOOD_PUB_KEY)

    def test_sign_payload(self):
        client = self.gen_client()
        signed = client.sign_payload({"hds.test.state": "Hello world!"})
        self.assertIn("hds.signature", signed.keys())
        # Check signature is valid, this will raise if not.
        verify_payload(GOOD_PUB_KEY, signed)

    def test_sign_payload_empty(self):
        client = self.gen_client()
        with self.assertRaises(HDSFailure):
            client.sign_payload({})
    
    def test_send_state(self):
        async def go():
            client = self.gen_client()
            await client.send_state("hds.test.state", "Foobar")
            self.assertEqual(len(client.mock_session.requests), 1)
            req = client.mock_session.requests[0]
            self.assertEqual(req["method"], "PUT")
            self.assertEqual(req["url"], "http://localhost:11111/_hds/hosts/%s/state/hds.test.state" % GOOD_PUB_KEY)
            self.assertEqual(req["json"]["hds.test.state"], "Foobar")
            self.assertEqual(req["json"]["hds.ttl"], 60 * 60 * 24)
            self.assertIsNotNone(req["json"]["hds.signature"])
        asyncio.run(go(), debug=True)

    def test_send_state_custom_ttl(self):
        async def go():
            client = self.gen_client()
            await client.send_state("hds.test.state", "Foobar", ttl=100)
            req = client.mock_session.requests[0]
            self.assertEqual(req["json"]["hds.ttl"], 100)
        asyncio.run(go(), debug=True)

    def test_send_state_bad_ttl(self):
        async def go():
            client = self.gen_client()
            with self.assertRaises(ValueError):
                await client.send_state("hds.test.state", "Foobar", ttl=9)
            with self.assertRaises(ValueError):
                await client.send_state("hds.test.state", "Foobar", ttl=0)
            with self.assertRaises(TypeError):
                await client.send_state("hds.test.state", "Foobar", ttl="apple")
            with self.assertRaises(ValueError):
                await client.send_state("hds.test.state", "Foobar", ttl=-15)
        asyncio.run(go(), debug=True)

    def test_put_topic_no_subtopic(self):
        async def go():
            client = self.gen_client()
            await client.put_topic("hds.test.topic")
            self.assertEqual(len(client.mock_session.requests), 1)
            req = client.mock_session.requests[0]
            self.assertEqual(req["method"], "PUT")
            self.assertEqual(req["url"], "http://localhost:11111/_hds/hosts/%s/topic/hds.test.topic" % GOOD_PUB_KEY)
            self.assertEqual(req["json"]["hds.test.topic"], [])
            self.assertIsNotNone(req["json"]["hds.signature"])
        asyncio.run(go(), debug=True)

    def test_put_topic_subtopic(self):
        async def go():
            client = self.gen_client()
            await client.put_topic("hds.test.topic", ["foo", "bar"])
            self.assertEqual(len(client.mock_session.requests), 1)
            req = client.mock_session.requests[0]
            self.assertEqual(req["method"], "PUT")
            self.assertEqual(req["url"], "http://localhost:11111/_hds/hosts/%s/topic/hds.test.topic" % GOOD_PUB_KEY)
            self.assertEqual(req["json"]["hds.test.topic"], ["foo", "bar"])
            self.assertIsNotNone(req["json"]["hds.signature"])
        asyncio.run(go(), debug=True)

    def test_get_topic_found(self):
        async def go():
            client = self.gen_client({
                "topics": {
                    "hds.test.topic": GOOD_PUB_KEY,
                }
            })
            res = await client.get_topic("hds.test.topic")
            self.assertEqual(len(client.mock_session.requests), 1)
            req = client.mock_session.requests[0]
            self.assertEqual(req["method"], "GET")
            self.assertEqual(req["url"], "http://localhost:11111/_hds/topics/hds.test.topic")
            self.assertEqual(res, {"hosts": GOOD_PUB_KEY})
        asyncio.run(go(), debug=True)

    def test_get_topic_missing(self):
        async def go():
            client = self.gen_client({
                "topics": { }
            })
            res = await client.get_topic("hds.test.topic")
            self.assertEqual(len(client.mock_session.requests), 1)
            req = client.mock_session.requests[0]
            self.assertEqual(req["method"], "GET")
            self.assertEqual(req["url"], "http://localhost:11111/_hds/topics/hds.test.topic")
            self.assertEqual(res, None)
        asyncio.run(go(), debug=True)

    def test_get_topic_empty(self):
        async def go():
            client = self.gen_client({
                "topics": { }
            })
            with self.assertRaises(ValueError):
                await client.get_topic("")
            with self.assertRaises(ValueError):
                await client.get_topic(None)
            with self.assertRaises(ValueError):
                await client.get_topic(123)
            with self.assertRaises(ValueError):
                await client.get_topic(bool)
        asyncio.run(go(), debug=True)

    def test_get_topic_subtopics(self):
        async def go():
            client = self.gen_client({
                "topics": {
                    "hds.test.topic/foo/bar": GOOD_PUB_KEY,
                }
            })
            res = await client.get_topic("hds.test.topic", ["foo", "bar"])
            self.assertEqual(len(client.mock_session.requests), 1)
            req = client.mock_session.requests[0]
            self.assertEqual(req["method"], "GET")
            self.assertEqual(req["url"], "http://localhost:11111/_hds/topics/hds.test.topic/foo/bar")
            self.assertEqual(res, {"hosts": GOOD_PUB_KEY})
        asyncio.run(go(), debug=True)

    def test_get_topics(self):
        async def go():
            client = self.gen_client({
                "all_topics": ["foo", "bar", "baz"]
            })
            res = await client.get_topics()
            self.assertEqual(len(client.mock_session.requests), 1)
            req = client.mock_session.requests[0]
            self.assertEqual(req["method"], "GET")
            self.assertEqual(req["url"], "http://localhost:11111/_hds/topics")
            self.assertEqual(res, ["foo", "bar", "baz"])
        asyncio.run(go(), debug=True)

    def test_get_state(self):
        async def go():
            # Generate a state payload
            client = self.gen_client({
                "state": {
                    GOOD_PUB_KEY: {
                        "hds.test.key": "Foobar",
                        "hds.test.key2": "Foobar2",
                        "hds.test.expired_key": "Barbaz",
                        "hds.expired": ["hds.test.expired_key"]
                    }
                }
            })
            res = await client.get_state(GOOD_PUB_KEY)
            self.assertEqual(len(client.mock_session.requests), 1)
            req = client.mock_session.requests[0]
            self.assertEqual(req["method"], "GET")
            self.assertEqual(req["url"], "http://localhost:11111/_hds/hosts/%s" % GOOD_PUB_KEY)
            self.assertIsNotNone(res)
            self.assertEqual(res["hds.test.key"], "Foobar")
            self.assertEqual(res["hds.test.key2"], "Foobar2")
            self.assertNotIn("hds.test.expired_key", res.keys())
        asyncio.run(go(), debug=True)

    def test_get_state_not_paranoid(self):
        async def go():
            # Generate a state payload
            client = self.gen_client({
                "state": {
                    GOOD_PUB_KEY: {
                        "hds.test.expired_key": "Barbaz",
                        "hds.expired": ["hds.test.expired_key"]
                    }
                }
            }, paranoid_mode=False)
            res = await client.get_state(GOOD_PUB_KEY)
            self.assertEqual(res["hds.test.expired_key"], "Barbaz")
        asyncio.run(go(), debug=True)

    def test_identify(self):
        async def go():
            # Generate a state payload
            client = self.gen_client()
            res = await client.identify()
            self.assertEqual(res, {'hds.servername': 'a_server_name', 'hds.type': 'hds.directory'})
        asyncio.run(go(), debug=True)