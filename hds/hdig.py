import asyncio
import logging
import argparse
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

    for host_name in topic_res["hosts"]:
        has_subtopics = len(host_values["subtopics"]) > 0
        print("  ", host_name[:32], "" if has_subtopics else ":No subtopic")
        if has_subtopics:
            print("    ", "\n    ".join(host_values["subtopics"]))


async def main():
    parser = argparse.ArgumentParser(description='dig for HDS - Request information about hosts from a host directory.')
    parser.add_argument('--host', type=str, default="http://localhost:27012",
                        help="Host to connect to, defaults to localhost"
    )
    parser.add_argument('req', type=str, choices=["identify", "host", "topics", "topic"], help="Action to perform")
    parser.add_argument('--host_or_topic', type=str, default=None, help="Only for host, topic")
    args = parser.parse_args()

    c = DirectoryClient(args.host)

    if args.req == "identify":
        await pretty_print_identify(c)
    elif args.req == "host":
        if args.host_or_topic is None:
            print("host not given")
            return
        await pretty_print_host(args.host_or_topic, c)
    elif args.req == "topics":
        print("Topics: " + "\n\t".join(await c.get_topics()))
    elif args.req == "topic":
        if args.host_or_topic is None:
            print("topic not given")
            return
        pretty_print_topic(await c.get_topic(args.host_or_topic))
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
