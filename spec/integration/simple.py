import logging
import asyncio
import time
from hds.client import DirectoryClient
from spec.integration.hds_runner import HDSRunner

logger = logging.getLogger(__name__)

KEY_PATH = "data/privkey.pem"

class SimpleTests:

    def __init__(self, runner: HDSRunner):
        self.runner = runner

    def run(self):
        logger.info("Running test cases")
        tests = [
            self.test_can_start,
            self.test_can_determine_identity,
            self.test_can_store_state,
            self.test_can_store_state_quickly,
            self.test_can_get_state,
            self.test_can_get_state_quickly,
            # self.test_can_federate,
            self.test_run_many,
        ]
        passes = 0
        fails = 0
        for test in tests:
            logger.info("Running %s", test.__name__)
            try:
                asyncio.run(test())
                passes += 1
            except AssertionError as e:
                logger.warn("Test failed [ASSERT] %s", e)
                fails += 1
            except Exception as e:
                logger.warn("Test failed [EXECPT] %s", e)
                fails += 1
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
        state = await c.get_state(c.get_pubkey())
        print(state)
    # async def test_can_federate(self):
    #    self.runner.create_hds()
    #    # Spawn the second
