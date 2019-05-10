import pymongo
import os
import logging
import time
import re

from ..util import HDSFailure

logger = logging.getLogger(__name__)
MONGOSTRING = os.environ.get("MONGOSTRING")


class Store():
    def __init__(self):
        logger.info("Starting new store instance")
        if MONGOSTRING is None:
            raise Exception("Enviroment variable MONGOSTRING is defined. Cannot continue.")
        logger.info("Connecting to %s", MONGOSTRING)
        self.client = pymongo.MongoClient(MONGOSTRING, socketTimeoutMS=2000)
        print(self.client)
        self.db = self.client.get_database()
        logger.info("Creating indexes..")
        self.db.get_collection("topics").create_index(
            [('topic', pymongo.ASCENDING)],
            unique=True
        )
        self.db.get_collection("server").create_index(
            [('server', pymongo.ASCENDING)],
            unique=True
        )

    def get_topics(self):
        db = self.client.get_database()
        topics = []
        for topic in db.get_collection("topics").find():
            topics.append(self.unescape_field_name(topic["topic"]))
        return topics

    def get_topic_hosts(self, topic, subtopic=None):
        topic = self.escape_field_name(topic)
        if subtopic is not None:
            subtopic = self.unescape_field_name(subtopic)
        db_topic: dict = self.db.get_collection("topics").find_one({
            "topic": topic,
        })
        if db_topic is None:
            return None
        hosts = {}
        for servername, details in db_topic.items():
            if servername == "_id" or servername == "topic":
                continue
            if subtopic is not None:
                match = False
                for x in details["subtopics"]:
                    if x.startswith(subtopic):
                        match = True
                        break
                if not match:
                    continue
            hosts[servername] = details
        return hosts

    def store_host_topic(self, server, topic: str, subtopics: list, signature):
        topics = self.client.get_database().get_collection("topics")
        topic = self.escape_field_name(topic)
        subtopics = [self.escape_field_name(x) for x in subtopics]
        topics.update_one({
            "topic": topic,
        }, {
            "$setOnInsert": {
                "topic": topic,
            },
            "$set": {
                server: {
                    "subtopics": subtopics,
                    "signature": signature,
                },
            }
        }, upsert=True)

    def get_host_state(self, server):
        hosts = self.client.get_database().get_collection("hosts")
        regx = re.compile("^" + server)
        results: dict = hosts.count_documents({"server": regx})
        if results == 0:
            raise HDSFailure("No hosts found", type="hds.error.hosts.none")
        elif results > 1:
            raise HDSFailure(
                "Multiple hosts found matching that ID",
                type="hds.error.hosts.conflict")

        db_host = hosts.find_one({"server": regx})

        if db_host is None:
            return None

        host = {
            "hds.expired": [],
        }
        for k in db_host.keys():
            val = db_host.get(k)
            if not isinstance(val, dict):
                continue
            key = self.unescape_field_name(k)
            host[key] = {
                "value": val.get("value"),
                "hds.signature": val.get("signature"),
                "hds.ttl": val.get("ttl"),
            }
            if int(time.time() * 1000) - val.get("last_updated") > (val.get("ttl") * 1000):
                host["hds.expired"].append(key)
                host["hds.expired"].append(key)
        return host

    def store_host_state(self, server, key, value, ttl, signature):
        hosts = self.client.get_database().get_collection("hosts")
        key = self.escape_field_name(key)
        if not isinstance(value, str) and not isinstance(value, int):
            raise Exception("Cannot store values that are not strings or integers")
        hosts.update_one({
            "server": server,
        }, {
            "$setOnInsert": {
                "server": server,
            },
            "$set": {
                key: {
                    "value": value,
                    "ttl": ttl,
                    "signature": signature,
                    "last_updated": int(time.time() * 1000)  # We want the milliseconds kept
                }
            }
        }, upsert=True)

    def escape_field_name(self, field: str):
        if "．" in field or "＄" in field:
            raise Exception("Cannot handle field names that contain U+FF04, U+FF0E")
        field = field.replace(".", "．")
        field = field.replace("$", "＄")
        return field

    def unescape_field_name(self, field: str):
        field = field.replace("．", ".")
        field = field.replace("＄", "$")
        return field
