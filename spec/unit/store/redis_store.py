import unittest
import fakeredis
from hds.store.redis_store import RedisStore
from time import sleep, time
from hds.util import HDSFailure
# import asyncio


class RedisStoreTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def createStore(self):
        r = RedisStore()
        r.r = fakeredis.FakeStrictRedis()
        return r

    def test_create_redis(self):
        self.createStore()

    def test_get_topics_none(self):
        r = self.createStore()
        topics = r.get_topics()
        self.assertEqual(len(topics), 0)

    def test_set_and_get_topics(self):
        r = self.createStore()
        r.store_host_topic("alice", "foo", [], "fakesig")
        r.store_host_topic("bob", "bar", [], "fakesig")
        r.store_host_topic("bob", "foo", [], "fakesig")
        r.store_host_topic("alice", "baz", [], "fakesig")
        self.assertSetEqual(
            set(r.get_topics()),
            set(["foo", "bar", "baz"])
        )

    def test_set_and_get_subtopics(self):
        r = self.createStore()
        r.store_host_state("alice", "hds.host", "hostname", 100, "fakesig")
        r.store_host_state("bob", "hds.host", "hostname", 100, "fakesig")
        r.store_host_topic("alice", "foo", ["bar"], "fakesig")
        r.store_host_topic("bob", "foo", ["baz"], "fakesig")
        r.store_host_topic("bob", "foo", ["baz", "foobar"], "fakesig")

        self.assertEqual(r.get_topic_hosts("foo", "bar"), ["alice"])
        self.assertEqual(r.get_topic_hosts("foo", "baz"), ["bob"])
        self.assertEqual(r.get_topic_hosts("foo", "baz/foobar"), [])
        self.assertEqual(r.get_topic_hosts("foo", "foobar"), ["bob"])

    def test_get_topic_hosts(self):
        r = self.createStore()
        # Need to store host state before we can store topics
        r.store_host_state("alice", "hds.host", "hostname", 100, "fakesig")
        r.store_host_topic("alice", "foo", [], "fakesig")
        r.store_host_state("bob", "hds.host", "hostname", 100, "fakesig")
        r.store_host_topic("bob", "foo", [], "fakesig")
        self.assertSetEqual(
            set(r.get_topic_hosts("foo")),
            set(["alice", "bob"])
        )
    
    def test_get_topic_hosts_expired(self):
        lu = time() - 1
        r = self.createStore()
        r.store_host_state("alice", "hds.host", "hostname", 1, "fakesig", lu)
        r.store_host_topic("alice", "foo", [], "fakesig")
        self.assertEqual(r.get_topic_hosts("foo"), ["alice"])
        sleep(1)
        self.assertEqual(r.get_topic_hosts("foo"), [])

    def test_set_and_get_state(self):
        r = self.createStore()
        la = int(time())
        r.store_host_state("alice", "hds.host", "hostname", 100, "fakesig", la)
        r.store_host_state("alice", "hds.test.expired", "expired", -1, "fakesig", la)
        r.store_host_state("alice", "hds.test.valid", "foobar", 100, "fakesig", la)
        res = r.get_host_state("alice")
        self.assertIn("hds.test.expired", res["hds.expired"])
        self.assertEqual(res["hds.test.expired"], {
            "hds.signature": "fakesig",
            "hds.ttl": -1,
            "value": "expired",
            "hds.last_updated": la})
        self.assertEqual(res["hds.test.valid"], {
            "hds.signature": "fakesig",
            "hds.ttl": 100,
            "value": "foobar",
            "hds.last_updated": la})
        self.assertEqual(res["hds.host"], {
            "hds.signature": "fakesig",
            "hds.ttl": 100,
            "value": "hostname",
            "hds.last_updated": la})

    def test_get_state_no_host(self):
        r = self.createStore()
        with self.assertRaises(HDSFailure):
            r.get_host_state("fakeserver")

    def test_find_host(self):
        r = self.createStore()
        r.store_host_state("alice", "hds.host", "hostname", 100, "fakesig")
        self.assertEqual(r.find_host("ali"), "alice")

    def test_find_host_conflict(self):
        r = self.createStore()
        r.store_host_state("alice", "hds.host", "hostname", 100, "fakesig")
        r.store_host_state("adam", "hds.host", "hostname", 100, "fakesig")
        with self.assertRaises(HDSFailure):
            r.find_host("a")

    def test_find_host_none(self):
        r = self.createStore()
        with self.assertRaises(HDSFailure):
            r.find_host("alice")
