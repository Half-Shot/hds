import logging
import asyncio
import time
from aiohttp import ClientSession
from hds.client import DirectoryClient
from hds.util.util import HDSFailure
from spec.integration.hds_runner import HDSRunner

logger = logging.getLogger(__name__)

KEY_PATH = "data/privkey.pem"

class SimpleTests:

    def __init__(self, runner: HDSRunner):
        self.runner = runner

    def run(self, test_whitelist=None, force_logging=False):
        logger.info("Running test cases")
        tests = [
            self.test_can_start,
            self.test_can_determine_identity,
            self.test_can_store_state,
            self.test_can_store_state_quickly,
            self.test_can_get_state,
            self.test_can_get_state_quickly,
            self.test_can_store_topic,
            self.test_can_store_subtopic,
            self.test_can_get_topic,
            self.test_can_get_topic_multiple_hosts,
            self.test_can_get_subtopic,
            self.test_run_many,
            self.test_memory_consumption_idle,
            self.test_memory_consumption_load,
            self.test_state_is_signed,
            self.test_topic_is_signed,
            self.test_keep_latest_state,
            self.test_fail_bad_strings,
            self.test_state_key_size,
            self.test_state_value_size,
            self.test_state_tombstone,
            self.test_fail_bad_signature,
        ]
        passes = 0
        fails = 0
        for test in tests:
            if test_whitelist is not None:
                if test.__name__ not in test_whitelist:
                    continue

            logger.info("Running %s", test.__name__)
            need_logs = force_logging
            try:
                asyncio.run(test())
                passes += 1
            except AssertionError as e:
                logger.warn("Test failed [ASSERT] %s", e)
                fails += 1
            except Exception as e:
                logger.warn("Test failed [EXECPT] %s", e)
                fails += 1
                need_logs = True

            if need_logs:
                self.runner.logs()
            self.runner.stop()
        return passes, fails

    async def test_can_start(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012")
        # If this doesn't throw, then it started okay
        await c.identify()

    async def test_can_determine_identity(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012")
        # If this doesn't throw, then it started okay
        identity = await c.identify()
        assert "hds.servername" in identity, "hds.servername not in identity response"
        assert "hds.type" in identity, "hds.type is not in identity response"
        assert identity["hds.type"] == "hds.directory", "hds.type is not hds.directory"

    async def test_can_store_state(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        await c.send_state("test.key", "value")

    async def test_can_store_state_quickly(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        # Time this one
        t = time.time_ns()
        await c.send_state("test.key", "value")
        t_end = (time.time_ns() - t) / (10 ** 6)
        logger.info("Took %dms", t_end)
        assert t_end < 50, "Time taken to store state must be under 50 milliseconds"

    async def test_can_get_state(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        r2 = c.send_state("hds.test1", "foo")
        r3 = c.send_state("hds.test2", "bar")
        r4 = c.send_state("hds.test3", "baz")
        await r2
        await r3
        await r4
        state = await c.get_state(c.get_pubkey())
        assert state["hds.host"] == "example.com", "hds.host was not found in state"
        assert state["hds.test1"] == "foo", "hds.test1 was not found in state"
        assert state["hds.test2"] == "bar", "hds.test2 was not found in state"
        assert state["hds.test3"] == "baz", "hds.test3 was not found in state"

    async def test_state_is_signed(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        expected_payload = c.sign_payload({"hds.ttl": 60, "hds.host": "example.com"})
        await c.send_state("hds.host", "example.com", 60)
        state = await c.get_state(c.get_pubkey(), raw=True)
        print(state, expected_payload)
        sig1 = state["hds.host"]["hds.signature"] 
        sig2 = expected_payload["hds.host"]["hds.signature"] 
        assert sig1 == sig2, "Signatures should match"

    async def test_topic_is_signed(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com", 60)
        await c.put_topic("hds.test.topic", ["topic1", "topic2"])
        topic_data = await c.get_host_topic(c.get_pubkey(), "hds.test.topic")
        print(topic_data)

    async def test_can_get_state_quickly(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        r2 = c.send_state("hds.test1", "foo")
        r3 = c.send_state("hds.test2", "bar")
        r4 = c.send_state("hds.test3", "baz")
        await r2
        await r3
        await r4
        # Time this one
        t = time.time_ns()
        await c.get_state(c.get_pubkey())
        t_end = (time.time_ns() - t) / (10 ** 6)
        logger.info("Took %dms", t_end)
        assert t_end < 50, "Time taken to store state must be under 50 milliseconds"

    async def test_run_many(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        p = []
        t = time.time_ns()
        for i in range(0, 100):
            p.append(c.send_state("hds.record_%d" % i, "This is record %d" % i))
        await asyncio.wait(p)
        t_end = (time.time_ns() - t) / (10 ** 6)
        logger.info("Took %dms", t_end)

    async def test_memory_consumption_idle(self):
        inst = self.runner.create_hds()
        stats = inst.stats(stream=False)["memory_stats"]
        max_usage = stats["max_usage"] / (1024 * 1024) # MB
        logger.info("Used %dMB", max_usage)
        assert max_usage < 50, "Memory usage must be under 50 MB"

    async def test_memory_consumption_load(self):
        inst = self.runner.create_hds()
        stats = inst.stats(stream=False)["memory_stats"]
        max_usage = 0

        # Generate rudimentary load by running 500 state puts
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        for n in range(0, 5):
            p = []
            for i in range(0, 100):
                p.append(c.send_state("hds.record_%d" % i, "This is record %d" % i))
            # Take a measurement at each stage
            max_usage = max(stats["max_usage"], max_usage)
            await asyncio.wait(p)
        
        max_usage = max_usage / (1024 * 1024) #MB
        logger.info("Used %dMB", max_usage)
        assert max_usage < 250, "Memory usage must be under 250 MB"

    async def test_can_store_topic(self):
        inst = self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        await c.put_topic("test.topic")

    async def test_can_store_subtopic(self):
        inst = self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        await c.put_topic("test.topic", ["subtopic", "anothersubtopic"])

    async def test_can_get_topic(self):
        inst = self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        await c.put_topic("test.topic")
        res = await c.get_topic("test.topic")
        assert c.get_pubkey() in res["hosts"]

    async def test_can_get_topic_multiple_hosts(self):
        inst = self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        c2 = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        await c2.send_state("hds.host", "example2.com")
        await c.put_topic("test.topic")
        await c2.put_topic("test.topic")

        res = await c.get_topic("test.topic")
        assert c.get_pubkey() in res["hosts"]
        assert c2.get_pubkey() in res["hosts"]

    async def test_can_get_subtopic(self):
        inst = self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        await c.put_topic("test.topic", ["subtopic", "anothersubtopic"])
        res = await c.get_topic("test.topic", ["subtopic"])
        print(res)
        assert c.get_pubkey() in res["hosts"]

    async def test_keep_latest_state(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        for i in range(0, 256):
            time.sleep(0.001)
            await c.send_state("hds.test." + str(i), "state" + str(i))
        state = await c.get_state(c.get_pubkey())
        assert state.get("hds.test.0") is None, "hds.test.0 should not exist"
        assert state.get("hds.host") is not None, "hds.host should always exist"
        assert len(state.keys()) == 255, "there should be no more than 255 state keys"

    async def test_fail_bad_strings(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        try:
            await c.send_state("hds.test.bad_value", 123)
            assert False, "Must throw"
        except HDSFailure as e:
            assert e.type == "hds.error.payload.bad_type", "Incorrect error type " + e.type

        try:
            await c.send_state("hds.test.bad_value", None)
            assert False, "Must throw"
        except HDSFailure as e:
            assert e.type == "hds.error.payload.bad_type", "Incorrect error type " + e.type

        try:
            await c.send_state("hds.test.bad_value", True)
            assert False, "Must throw"
        except HDSFailure as e:
            assert e.type == "hds.error.payload.bad_type", "Incorrect error type " + e.type

    async def test_state_key_size(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")

        try:
            await c.send_state("a", "too small")
            assert False, "Must throw"
        except HDSFailure as e:
            assert e.type == "hds.error.payload.key_too_short", "Incorrect error type " + e.type

        try:
            await c.send_state("aa", "too small")
            assert False, "Must throw"
        except HDSFailure as e:
            assert e.type == "hds.error.payload.key_too_short", "Incorrect error type " + e.type

        await c.send_state("a" * 1024, "should be fine")

        try:
            await c.send_state("a" * 1025, "too large")
            assert False, "Must throw"
        except HDSFailure as e:
            assert e.type == "hds.error.payload.key_too_long", "Incorrect error type " + e.type

    async def test_state_value_size(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")

        try:
            await c.send_state("hds.small_value", "")
            assert False, "Must throw"
        except HDSFailure as e:
            assert e.type == "hds.error.payload.body_too_short", "Incorrect error type " + e.type

        try:
            await c.send_state("hds.body_too_long", "a" * ((1024 * 64) + 1))
            assert False, "Must throw"
        except HDSFailure as e:
            assert e.type == "hds.error.payload.body_too_long", "Incorrect error type " + e.type

        await c.send_state("hds.body_too_long", "a" * (1024 * 64))

    async def _raw_state_send(self, c, key, payload):
        baseurl = DirectoryClient.format_baseurl(c.base_url)
        async with ClientSession() as session:
            url = "{}/hosts/{}/state/{}".format(baseurl, c.pub_key, key)
            res = await session.put(url=url, json=payload, ssl=False)
            if res.status == 201:
                return
            DirectoryClient.check_error(await res.json())

    async def test_fail_bad_signature(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        payload = c.sign_payload({"hds.ttl": 60, "hds.foo": "bar"})
        # This should succeed
        await self._raw_state_send(c, "hds.foo", payload)

        try:
            payload["hds.signature"] = "notarealsig"
            await self._raw_state_send(c, "hds.foo", payload)
            assert False, "Must throw"
        except HDSFailure as e:
            assert e.type == "hds.error.payload.bad_signature", "Incorrect error type " + e.type

        try:
            del payload["hds.signature"]
            await self._raw_state_send(c, "hds.foo", payload)
            assert False, "Must throw"
        except HDSFailure as e:
            assert e.type == "hds.error.payload.missing_key", "Incorrect error type " + e.type

        # TODO: Check hds.error.servername.not_rsa

        # hds.error.payload.bad_signature
        try:
            payload["hds.signature"] = c.sign_payload({"hds.ttl": 60, "hds.foo": "baz"})["hds.signature"]
            await self._raw_state_send(c, "hds.foo", payload)
            assert False, "Must throw"
        except HDSFailure as e:
            assert e.type == "hds.error.payload.bad_signature", "Incorrect error type " + e.type

    async def test_state_tombstone(self):
        self.runner.create_hds()
        c = DirectoryClient("http://localhost:27012", private_key_path=KEY_PATH)
        await c.send_state("hds.host", "example.com")
        await c.send_state("hds.tombstone", "was hacked")
        try:
            await c.send_state("hds.newdata", "was hacked")
            assert False, "Must throw"
        except HDSFailure as e:
            assert e.type == "hds.error.host.tombstone", "Incorrect error type " + e.type



    # async def test_can_federate(self):
    #    self.runner.create_hds()
    #    # Spawn the second
