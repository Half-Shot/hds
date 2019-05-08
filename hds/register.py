import asyncio
import logging
import argparse
from pathlib import Path
import sys
from os import environ
from time import sleep
from os.path import exists
from .client import DirectoryClient, generate_key

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

DEFAULT_KEY_LOCATION = Path.joinpath(Path.home(), ".hds/private.pem")
TTL = 60 * 60 * 24 * 1


async def main(args):
    logger.warning("Starting HDS registration service")
    if cliArgs.host:
        host = cliArgs.host
    else:
        host = environ.get("HDS_HOST", "127.0.0.1:27012")

    # 0. Generate, if needed.
    if args.generate_keys:
        # Generate the keys first
        if exists(args.key):
            logger.critical("Key exists, will not generate")
            sys.exit(1)
        else:
            logger.info("Generating new key...")
            Path(args.key).parent.mkdir(parents=True, exist_ok=True)
            key = generate_key()
            with open(args.key, "w") as f:
                f.write(key.decode())
            logger.info("Key written to %s", args.key)

    if await pre_flight_checks(host) is False:
        sys.exit(1)
    client = DirectoryClient(base_url=host, private_key_path=args.key)
    topics = {}
    for topic in args.topics:
        topic_split = topic.split("=")
        topic_name = topic_split[0]
        if len(topic_split) > 1:
            topics[topic_name] = topic_split[1].split(",")
        else:
            topics[topic_name] = []
    state = {}
    for st in args.state:
        st_split = st.split("=")
        state_name = st_split[0]
        if len(st_split) > 1:
            state[state_name] = st_split[1]
        else:
            state[state_name] = ""
    state_host = state.pop("hds.host", None)
    state["hds.ttl"] = int(state.pop("hds.ttl"))
    run = True
    logger.info("FYI, my key is: %s" % client.get_pubkey())
    while run:
        tasks = []
        logger.info("Sending state and topics...")
        if state_host is not None:
            logger.debug("Sending host %s" % (state_host))
            await client.send_state("hds.host", state_host)
            logger.debug("Sent host")
        for state_name, state_value in state.items():
            logger.debug("Sending state %s = %s" % (state_name, state_value))
            tasks.append(client.send_state(state_name, state_value))
        for topic_name, topic_value in topics.items():
            logger.debug("Sending topic %s = %s" % (topic_name, topic_value))
            tasks.append(client.put_topic(topic_name, topic_value))
        await asyncio.wait(tasks)
        logger.info("Done...")
        run = args.daemon
        if run:
            sleep(TTL - 60)
    # 2. Check our keys


async def pre_flight_checks(host):
    expected_identity = environ.get("HDS_RES_HOST_IDENTITY")
    # Check the host
    try:
        client = DirectoryClient(base_url=host)
        identity = await client.identify()
        if expected_identity is not None:
            if identity["hds.servername"] != expected_identity:
                logger.critical("Host identity does NOT match expected identity. Cannot continue")
                sys.exit(1)
        else:
            logger.warning(
                "Not checking host identity! Assuming %s is trusted",
                identity["hds.servername"][:32]
            )
    except Exception as ex:
        logger.critical("Couldn't connect to HDS, is it running? %s", ex)
        sys.exit(1)
    logger.info("Host identity confirmed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('-d', '--daemon', dest='daemon', action='store_true', default=False,
                        help='Run continuously')
    parser.add_argument('-g', '--generate-keys', dest='generate_keys', action='store_true',
                        default=False,
                        help='Generate a public private key pair')
    parser.add_argument('-k', '--key', dest='key', action='store', type=str,
                        default=DEFAULT_KEY_LOCATION,
                        help='Path where the private key is stored')
    parser.add_argument('--host', dest='host', action='store', type=str, default=None,
                        help='Host to set state on')
    parser.add_argument('-t', '--topic', dest='topics', action='store', default=[],
                        help='Topics', nargs='+')
    parser.add_argument('-s', '--state', dest='state', action='store', default=[],
                        help='Topics', nargs='+')

    cliArgs = parser.parse_args()
    asyncio.get_event_loop().run_until_complete(main(cliArgs))

    # asyncio.run(c.send_state(DirectoryClient.HDS_HOST, "127.0.0.1", ttl=ONE_DAY))
    # asyncio.run(c.send_state("hds.name", "Half-Shot's local box", ttl=ONE_DAY))
    # asyncio.run(c.send_state("hds.contact.email", "will@half-shot.uk", ttl=ONE_DAY))
    # asyncio.run(c.send_state("hds.countrycode", "GB", ttl=ONE_DAY))
    # asyncio.run(c.put_topic("an.example.topic"))
    # asyncio.run(c.put_topic("topics.with.subs", ["heavy", "weapons.guy"]))
