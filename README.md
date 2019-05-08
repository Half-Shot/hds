# hds
Protocol documentation and code for the HDS protocol.

## Protocol

The protocol documentation can be found under `protocol/` in markdown format. Documentation for the
service must be generated by calling `make html` (you need to follow the steps for creating a virtual environment below first).

## Directory Service

The directory service and directory client library can be found under `hds/`.
### Installing using Docker (easier)

Running the service using the provided Dockerfile and docker-compose.yaml is
recommended as it will handle configuration of the service, and start Redis for you.

Dependency list (ubuntu packages):
- docker
- docker-compose

To run the service, simply run:

```
git checkout https://github.com/Half-Shot/hds.git
cd hds
mkdir data
openssl genrsa -out data/privkey.pem 4096
docker-compose up
```

which will run the directory service with a redis instance. You can use `docker-compose up -d` to
run it in detached mode so it will keep running in the background. You may wish to modify the
`docker-compose.yaml` to include your own contact details, as the service will automatically register
itself on startup.

### Installing directly onto the system

You'll need to install some dependencies in order to run the service. These instructions are
tested under a Ubuntu 19.04 (Linux) installation, so instructions may differ for your environment.

This assumes you have a redis database running locally, otherwise supply the `REDIS_HOST` environment
variable which points to the host providing the redis database.

Dependency list (ubuntu packages):
- python3
- virtualenv
- openssl

```
git checkout https://github.com/Half-Shot/hds.git
cd hds
virtualenv -p python3.7 env
source env/bin/activate
pip3 install -r requirements.txt
openssl genrsa -out privkey.pem 4096
HDS_PRIVKEY_PATH=privkey.pem python3 -m hds.directoryservice
```

Whichever way you started the service, you should now be able to run:

`curl http://localhost:27012/_hds/identify`

which should give you the identity of your brand new host.

## Tools

In order to run the tools, you will need to constuct a virtual environment as explained above.

Tools you can run:
- `python3 -m hds.hdig` A service for querying directory servers
- `python3 -m hds.register` A service for registering a service with a directory.

For help on how to use these tools, call them with the argument `--help`.

## Tests

Unit tests can be run by calling `python3 -m spec.unit.test`

The integration tests will require docker in order to run, as it uses Docker as a sandboxing method. Ensure
that you have installed docker and then run `python3 -m spec.integration.run`. This will not run if
the port `27012` is in use.