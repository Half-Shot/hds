import docker
import logging
import base64
import time
from hds.client.gen_key import generate_key
HDS_IMAGE = "project_hds:latest"
NET_NAME = "hds_test_net"
CONTAINER_NAME = "hds_test_con"

logger = logging.getLogger(__name__)

class HDSRunner:
    def __init__(self, docker_client: docker.DockerClient):
        self.docker = docker_client
        self.instance_set = []
        self.network = None
        self.counter = 0

    def setup(self):
        self.network = self.docker.networks.create(NET_NAME, driver="bridge")

    def tear_down(self):
        self.network.remove()

    def create_hds(self, contact_name: str = "Example Name", contact_email: str = "name@example.com"):
        self.counter += 1
        instance_redis = self.docker.containers.run(
            image="redis:alpine",
            network=NET_NAME,
            name="hds_test_redis_" + str(self.counter),
            detach=True
        )
        key = generate_key()
        instance = self.docker.containers.run(
            image=HDS_IMAGE,
            network=NET_NAME,
            name=CONTAINER_NAME + "_" + str(self.counter),
            environment={
                "HDS_CONTACT_NAME": contact_name,
                "HDS_CONTACT_EMAIL": contact_email,
                "REDIS_HOST": "hds_test_redis_" + str(self.counter),
                "HDS_PRIVKEY_DATA": base64.b64encode(key)
            },
            ports={"27012/tcp": "27012/tcp"},
            detach=True
        )
        self.instance_set.append(tuple([instance, instance_redis]))
        logger.info("Starting container")
        time.sleep(1)
        return instance

    def logs(self):
        if len(self.instance_set) == 0:
            return
        logger.info("=== Start of instance logs ===")
        l = self.instance_set[0][0].logs()
        if isinstance(l, bytes):
            l = l.decode().split("\n")
        for log in l:
            logger.info("INST: " + log)
        logger.info("=== End of instance logs ===")

    def stop(self):
        for instances in self.instance_set:
            instances[0].stop()
            instances[1].stop()
            instances[0].remove()
            instances[1].remove()
            self.counter -= 1
        self.instance_set.clear()