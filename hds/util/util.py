import base64
import base58
import logging
from os import environ
from canonicaljson import encode_canonical_json
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import utils
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_public_key

logger = logging.getLogger(__name__)


class HDSFailure(Exception):
    def __init__(self, msg, type="hds.error.unknown"):
        super().__init__(msg)
        self.type = type


class HDSBadKeyFailure(HDSFailure):
    def __init__(self, msg, inner_ex=None, type="hds.error.badkey"):
        super().__init__(msg)
        self.inner_ex = inner_ex
        self.msg = msg


def verify_payload(b58_server_key, body):
    """
    :param b58_server_key:
    :param body:
    :return:
    """
    try:
        encSig = body.get("hds.signature")
        sig = base64.b64decode(encSig)
    except Exception as e:
        logger.warning("Failed trying to decode signature %s", e)
        raise HDSFailure("Could not decode signature bytes", type="hds.error.payload.bad_signature")

    public_key = load_der_public_key(base58.b58decode(b58_server_key), backend=default_backend())

    if not isinstance(public_key, rsa.RSAPublicKey):
        logger.warning("Servername is not a RSA public key")
        raise HDSFailure("Not a RSA public key", type="hds.error.servername.not_rsa")
    sig_body = body
    del sig_body["hds.signature"]
    logger.debug("verify_payload %s %s", encSig, str(sig_body))
    try:
        public_key.verify(
            sig,
            encode_canonical_json(sig_body),
            padding.PSS(
                mgf=padding.MGF1(utils.hashes.SHA512()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            utils.hashes.SHA512()
        )
    except Exception:
        logger.error("Signature didn't match!")
        raise HDSFailure("Signature failed to verify", type="hds.error.payload.bad_signature")


def determine_our_host():
    return environ.get("HDS_HOST")
