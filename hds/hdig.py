import asyncio
import logging
from .client import DirectoryClient
from sys import argv


def print_error(err_res):
    if err_res.get("hds.error", False):
        print("Operation failed: %s (%s)" % (err_res["hds.error.text"], err_res["hds.error"]))
        return True


async def pretty_print_identify(c: DirectoryClient):
    identity = await c.identify()
    if print_error(identity):
        return
    print(
        """Host: {}
Type: {}""".format(identity["hds.servername"], identity["hds.type"]))


async def pretty_print_host(server_name, c):
    state = await c.get_state(
        server_name
    )
    if print_error(state):
        return
    print(
        """Host: {}
Name: {}
Owner: {}
Contact: {}
Country: {}
Servername (short): {}""".format(
            state.get("hds.host", "None set"),
            state.get("hds.name", "None set"),
            state.get("hds.contact.name", "None set"),
            state.get("hds.contact.email", "None set"),
            state.get("hds.countrycode", "None set"),
            server_name[:24]))


def pretty_print_topic(topic_res):
    if print_error(topic_res):
        return
    print("Hosts that support the topic:")
    for host_name, host_values in topic_res["hosts"].items():
        has_subtopics = len(host_values["subtopics"]) > 0
        print("  ", host_name[:32], "" if has_subtopics else ":No subtopic")
        if has_subtopics:
            print("    ", "\n    ".join(host_values["subtopics"]))


async def main():
    host = argv[1] if len(argv) > 2 else "http://localhost"
    if not host.startswith("http"):
        host = "https://" + host
    host += ":27012"
    c = DirectoryClient(host)
    req_type = argv[2] if len(argv) > 2 else argv[1]
    if req_type == "identify":
        await pretty_print_identify(c)
    elif req_type == "host":
        req_value = argv[3]
        await pretty_print_host(req_value, c)
    elif req_type == "all_topics" or req_type == "topics":
        print("Topics: " + "\n\t".join(await c.get_topics()))
    elif req_type == "topic":
        req_value = argv[3]
        pretty_print_topic(await c.get_topic(req_value))
    else:
        print("Request type not understood")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.get_event_loop().run_until_complete(main())

    # asyncio.run(c.send_state(DirectoryClient.HDS_HOST, "127.0.0.1", ttl=ONE_DAY))
    # asyncio.run(c.send_state("hds.name", "Half-Shot's local box", ttl=ONE_DAY))
    # asyncio.run(c.send_state("hds.contact.email", "will@half-shot.uk", ttl=ONE_DAY))
    # asyncio.run(c.send_state("hds.countrycode", "GB", ttl=ONE_DAY))
    # asyncio.run(c.put_topic("an.example.topic"))
    # asyncio.run(c.put_topic("topics.with.subs", ["heavy", "weapons.guy"]))