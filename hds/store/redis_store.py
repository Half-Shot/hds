import logging
import os
import time
import redis

from ..util import HDSFailure

HOST = os.environ.get("REDIS_HOST", "localhost")
PORT = int(os.environ.get("REDIS_PORT", "6379"))
PASSWORD = os.environ.get("REDIS_PASSWORD", None)

logger = logging.getLogger(__name__)

K_TOPICS = "hds/topics"
K_HOSTS = "hds/hosts"
K_TOPIC_HOSTS = "hds/topic/%s/hosts"
K_TOPIC_HOST_SIG = "hds/topic/%s/host/%s/signature"
K_TOPIC_SUBTOPIC_HOSTS = "hds/topic/%s/hosts/%s/subtopics"
K_HOST_STATE = "hds/host/%s/state/%s"
K_HOST_STATE_KEYS = "hds/host/%s/state"

HOST_STATE_FORMAT = "%s:%i:%i:%s"
STATE_STORAGE_LIMIT = 255

# Topic

# This implementation makes use of Redis rather than MongoDB which means queries should be faster.
#
# Topics are just:
# hds/topics => LIST
# hds/hosts => LIST
# hds/topic/{topic}/hosts => LIST host
# hds/topic/{topic}/host/{host}/signature => STR
# hds/topic/{topic}/hosts/{host}/subtopics => LIST
# hds/host/{host}/state/{key} => STR signature:ttl:last_updated:value
# hds/host/state => LIST keys


def curr_time():
    return int(time.time() * 1000)


class RedisStore():
    def __init__(self):
        logger.info("Starting new redis store instance")

        self.r = redis.Redis(
            host=HOST,
            port=PORT,
            password=PASSWORD)

        logger.info("Connecting to %s", HOST)

    def get_topics(self):
        """
        Get all topics found in the store.

        :return: A list of topic strings
        """
        logger.debug("redis://%s" % K_TOPICS)
        return [t.decode() for t in self.r.lrange(K_TOPICS, 0, -1)]

    def get_topic_hosts(self, topic, subtopics=None):
        """
        Get all hosts which implement the topic, and optionally the subtopics(s).

        :param topic: A topic string
        :param subtopic: A list of subtopics. Optional
        :return: A dict of hosts
        """
        path = K_TOPIC_HOSTS % topic
        topic_hosts = [host.decode() for host in self.r.lrange(path, 0, -1)
                       if not self.has_host_expired(host.decode()) and
                       not self.is_host_tombstoned(host.decode(), throw=False)]
        hosts = {}
        for host in topic_hosts:
            sig = self.r.get(K_TOPIC_HOST_SIG % (topic, host)).decode()
            host_entry = {
                "hds.signature": sig,
            }

            host_entry["subtopics"] = [
                s.decode() for s in self.r.lrange(K_TOPIC_SUBTOPIC_HOSTS % (topic, host), 0, -1)
            ]
            print(topic, subtopics)
            print(host, host_entry)

            if subtopics is not None:
                for i in range(len(subtopics)):
                    if subtopics[i] not in host_entry["subtopics"][i]:
                        host_entry = None
                        break
            if host_entry is not None:
                hosts[host] = host_entry
        return hosts

    def store_host_topic(self, server, topic: str, subtopics: list, signature):
        """
        Store a topic for a host

        :param server: The server name string
        :param topic: The topic string to store
        :param subtopics: A set of subtopics to store
        :param signature: Signature of the payload
        :return:
        """
        self.is_host_tombstoned(server)
        # Store the topic in the master list if its not there already
        if topic not in [t.decode() for t in self.r.lrange(K_TOPICS, 0, -1)]:
            logger.debug("Added %s to %s" % (topic, K_TOPICS))
            self.r.lpush(K_TOPICS, topic)

        # Store the host in the topic
        if server not in [s.decode() for s in self.r.lrange(K_TOPIC_HOSTS % topic, 0, -1)]:
            logger.debug("Added %s/%s to %s" % (topic, server, K_TOPIC_HOSTS % topic))
            self.r.lpush(K_TOPIC_HOSTS % topic, server)

        if len(subtopics) > 0:
            self.r.delete(K_TOPIC_SUBTOPIC_HOSTS % (topic, server))
            for subtopic in subtopics:
                self.r.lpush(K_TOPIC_SUBTOPIC_HOSTS % (topic, server), subtopic)
                print(K_TOPIC_SUBTOPIC_HOSTS % (topic, server), subtopics)

        self.r.set(K_TOPIC_HOST_SIG % (topic, server), signature)

    def get_host_state(self, server):
        """
        Get the full state of a given host

        :param server: The server name string
        :return: A object containing all the state of the host
        """
        server = self.find_host(server)
        state = {
            "hds.expired": [],
        }
        # Get all keys
        for key in self.r.lrange(K_HOST_STATE_KEYS % server, 0, -1):
            key = key.decode()
            vals = self.r.get(K_HOST_STATE % (server, key)).decode().split(":", 3)
            ttl = int(vals[1])
            last_updated = int(vals[2])
            state[key] = {
                "hds.signature": vals[0],
                "hds.ttl": ttl,
                "hds.last_updated": last_updated,
                "value": vals[3],
            }
            if curr_time() - last_updated > ttl:
                state["hds.expired"].append(key)
        return state

    def has_host_expired(self, server):
        """
        Determine if the host has expired, by checking it's 'hds.host' state value.
        :param server: The server name string

        :return: True if expired, False otherwise
        """
        vals = self.r.get(K_HOST_STATE % (server, "hds.host")).decode().split(":", 3)
        ttl = int(vals[1]) * 1000
        last_updated = int(vals[2])
        return curr_time() - last_updated > ttl

    def find_host(self, server):
        """
        Find a host by a partial or full servername. Will return a match if exactly
        one hosts matches, otherwise will throw a HDSFailure exception.

        :param server: The server name string, either partial or full
        :return: A full server name.
        """
        servers = [
            s.decode() for s in self.r.lrange(K_HOSTS, 0, -1) if s.decode().startswith(server)]
        if len(servers) == 0:
            raise HDSFailure("No hosts found", type="hds.error.hosts.none")
        elif len(servers) > 1:
            raise HDSFailure(
                "Multiple hosts found matching that ID",
                type="hds.error.hosts.conflict")
        return servers[0]

    def store_host_state(self, server, key, value, ttl, signature, last_updated=None):
        """
        Store a hosts state key and value

        :param server: The server name string
        :param key: The state key string
        :param value: The state value string
        :param ttl: The time to live for the key
        :param signature: The signature of the key value set
        :param last_updated: The time of the state update, will use current time if not defined
        """
        self.is_host_tombstoned(server)
        last_updated = curr_time() if last_updated is None else last_updated
        store_val = HOST_STATE_FORMAT % (signature, ttl, last_updated, value)
        existing_keys = [s.decode() for s in self.r.lrange(K_HOST_STATE_KEYS % server, 0, -1)]
        if server not in [s.decode() for s in self.r.lrange(K_HOSTS, 0, -1)]:
            self.r.lpush(K_HOSTS, server)
        if key not in existing_keys:
            logger.debug("Added new key %s to %s" % (key, server[:16]))
            self.r.lpush(K_HOST_STATE_KEYS % server, key)
        logger.debug("Updated key %s for %s" % (key, server[:16]))
        self.r.set(K_HOST_STATE % (server, key), store_val)
        self._check_host_state_size(server, len(existing_keys))

    def is_host_tombstoned(self, server, throw=True):
        if self.r.get(K_HOST_STATE % (server, "hds.tombstone")) is not None:
            if throw:
                raise HDSFailure("Host is tombstoned, it cannot be used",
                                 type="hds.error.host.tombstone")
            return True
        return False

    def _check_host_state_size(self, server, keysize: int):
        if keysize > STATE_STORAGE_LIMIT:
            full_state = self.get_host_state(server)
            while len(full_state.keys()) > STATE_STORAGE_LIMIT + 1:  # + 1 for hds.expired
                key_to_remove = None
                oldest_ts = 9223372036854775807  # maxint
                # TODO: refactor this
                for k, v in full_state.items():
                    if k == "hds.expired" or k == "hds.host":
                        continue
                    upd = v.get("hds.last_updated")
                    if upd < oldest_ts:
                        oldest_ts = upd
                        key_to_remove = k
                logger.debug(
                    "Removed key %s for %s as it has exceeded the key count" %
                    (key_to_remove, server)
                )
                del full_state[key_to_remove]
                self.r.lrem(K_HOST_STATE_KEYS % server, 1, key_to_remove)
