import logging;
import docker
import sys
from spec.integration.simple import SimpleTests
from spec.integration.hds_runner import HDSRunner

logger = logging.getLogger(__name__)

REQUIRED_IMAGES = set(["project_hds:latest", "redis:alpine"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting integration tester")
    logging.info("Connecting to docker")
    client = docker.from_env()
    image_tags = set()
    for image in client.images.list():
        if len(image.attrs["RepoTags"]) > 0:
            image_tags.add(image.attrs["RepoTags"][0])

    missing = REQUIRED_IMAGES - image_tags
    if len(missing) > 0:
        logging.error("Missing images: %s so tests will not run", str(missing))
    else:
        logging.info("All images accounted for")
    logging.info("Running ubuntu image")
    result = client.containers.run("hello-world")
    if result.decode().startswith("\nHello from Docker!"):
        logging.info("Docker is working!")
    else:
        logging.error("Docker isn't working correctly, cannot run tests")

    runner = HDSRunner(client)

    try:
        runner.setup()
        tests = SimpleTests(runner)
        passes, fails = tests.run()
    finally:
        runner.tear_down()

    if fails > 0:
        logger.error("FAIL: %d  / %d tests passed", passes, fails + passes)
        sys.exit(1)
    else:
        logger.info("SUCCESS: All %d tests passed", passes)
        sys.exit(0)
