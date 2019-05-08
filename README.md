# hds
Protocol documentation and code for the HDS protocol.

## Directory Service

The directory service and directory client library can be found under `hds/`.

### How to run the service

You'll need to install some dependencies in order to run the service.These instructions are tested under a Ubuntu 19.04 (Linux) installation, so instructions may differ for your environment.

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
openssl genrsa -out privkey.key 4096
```

## Protocol

The protocol documentation can be found under `protocol/`.
