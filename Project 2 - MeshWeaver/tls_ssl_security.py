

"""
tls.py
------
Module: TLS/SSL Security.

Two separate protections, both required by the problem statement:

1. TRANSPORT ENCRYPTION -- wraps the TCP traffic between nodes in TLS, so
   task payloads can't be read or tampered with by anyone sniffing the
   network. Implemented as `SecureNode`, a subclass of asyn.Node that
   swaps plaintext TCP for TLS-wrapped TCP. UDP (used only for cheap
   PING/PONG liveness checks) is left as-is, matching typical mesh design
   -- only the channel carrying actual task code+data needs to be encrypted.

2. REQUEST SIGNING -- proves WHO sent a task, so a node never executes
   code just because *something* on the network asked it to. Each node
   has an RSA keypair; it signs every task it submits, and a receiving
   node only executes the task if the signature verifies against a
   public key it already trusts for that sender.

Builds on:
  - async_networking.Node                              (Module 1: transport)
  - task_serialization.serialize_task / deserialize_task (task packaging)
"""

import asyncio
import datetime
import ssl
import tempfile
import os
import logging

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

from async_networking import Node, Message
from remote_task_execution import TaskExecutionError
from task_serialization import serialize_task, deserialize_task

logger = logging.getLogger("meshweaver.tls")

SECURE_TASK_SUBMIT = "SECURE_TASK_SUBMIT"
SECURE_TASK_RESULT = "SECURE_TASK_RESULT"


# ============================================================
# Part 1: TLS transport encryption
# ============================================================

def generate_self_signed_cert(common_name: str = "meshweaver-node"):
    """
    Generates a fresh self-signed TLS certificate + private key.
    Returns (cert_pem_bytes, key_pem_bytes).

    Note: self-signed certs are fine for a peer-to-peer mesh where nodes
    verify each other by pinning known certs/public keys (see Part 2's
    signature layer for the real trust mechanism) rather than relying on
    a central Certificate Authority -- there is no central authority in
    this design by definition.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def _write_temp_pem(pem_bytes: bytes) -> str:
    """ssl.SSLContext needs file paths, so write PEM bytes to a temp file."""
    fd, path = tempfile.mkstemp(suffix=".pem")
    with os.fdopen(fd, "wb") as f:
        f.write(pem_bytes)
    return path


class SecureNode(Node):
    """
    Drop-in replacement for asyn.Node that encrypts all TCP traffic with
    TLS. UDP ping/pong is left plaintext (cheap liveness checks only --
    no task data ever goes over UDP in this design).
    """

    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 0):
        super().__init__(node_id, host, port)
        cert_pem, key_pem = generate_self_signed_cert(common_name=node_id)
        self._cert_path = _write_temp_pem(cert_pem)
        self._key_path = _write_temp_pem(key_pem)
        self.cert_pem = cert_pem  # exposed so peers can pin/trust it if desired

    async def start(self):
        loop = asyncio.get_running_loop()

        # UDP stays plaintext -- only liveness pings travel here.
        from async_networking import _UDPProtocol
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self), local_addr=(self.host, self.port)
        )
        self._udp_transport = transport
        self.port = transport.get_extra_info("sockname")[1]

        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.load_cert_chain(self._cert_path, self._key_path)

        self._tcp_server = await asyncio.start_server(
            self._handle_tcp_connection, host=self.host, port=self.port, ssl=server_ctx
        )
        logger.info("SecureNode %s listening on %s:%s (UDP plaintext + TCP/TLS)", self.node_id, self.host, self.port)
        return self

    async def send_tcp(self, host, port, message, wait_response=True, timeout=5.0):
        # Demo-grade trust: accept any peer cert (self-signed, no shared CA)
        # but still get full encryption of the data in transit. Production
        # deployments would pin expected certs per known peer here instead.
        client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        client_ctx.check_hostname = False
        client_ctx.verify_mode = ssl.CERT_NONE

        from async_networking import _write_framed, _read_framed
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=client_ctx), timeout=timeout
        )
        try:
            _write_framed(writer, message.to_bytes())
            await writer.drain()
            if not wait_response:
                return None
            data = await asyncio.wait_for(_read_framed(reader), timeout=timeout)
            return Message.from_bytes(data) if data else None
        finally:
            writer.close()
            await writer.wait_closed()

    async def stop(self):
        await super().stop()
        for path in (self._cert_path, self._key_path):
            try:
                os.remove(path)
            except OSError:
                pass


# ============================================================
# Part 2: cryptographic request signing
# ============================================================

def generate_signing_keypair():
    """Each node's identity keypair, separate from its TLS cert."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def sign_bytes(private_key, data: bytes) -> bytes:
    return private_key.sign(
        data,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )


def verify_signature(public_key, data: bytes, signature: bytes) -> bool:
    try:
        public_key.verify(
            signature,
            data,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def public_key_to_pem(public_key) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def public_key_from_pem(pem_bytes: bytes):
    return serialization.load_pem_public_key(pem_bytes)


class SecureExecutor:
    """
    Like remote.RemoteExecutor, but every task must be signed by the
    sender and is only executed if the signature verifies against a
    public key this node already trusts for that sender.
    """

    def __init__(self, node: SecureNode, private_key, trusted_keys: dict = None):
        self.node = node
        self.private_key = private_key
        self.public_key = private_key.public_key()
        # node_id -> public_key, pre-shared trust (a real mesh would
        # exchange these during peer discovery / handshake)
        self.trusted_keys = trusted_keys or {}
        self.node.register_handler(SECURE_TASK_SUBMIT, self._on_secure_task_submit)

    def trust_peer(self, node_id: str, public_key):
        self.trusted_keys[node_id] = public_key

    async def submit_task(self, host: str, port: int, func, *args, timeout: float = 10.0, **kwargs):
        task_bytes = serialize_task(func, *args, **kwargs)
        signature = sign_bytes(self.private_key, task_bytes)

        message = Message(
            SECURE_TASK_SUBMIT,
            self.node.node_id,
            payload={"task": task_bytes.hex(), "signature": signature.hex()},
        )
        reply = await self.node.send_tcp(host, port, message, timeout=timeout)
        if reply is None:
            raise TimeoutError("No response received from remote node")

        status = reply.payload.get("status")
        if status == "ok":
            import cloudpickle
            return cloudpickle.loads(bytes.fromhex(reply.payload["result"]))
        elif status == "rejected":
            raise PermissionError(reply.payload.get("reason", "task rejected"))
        else:
            raise TaskExecutionError(reply.payload.get("error", "unknown error"))

    async def _on_secure_task_submit(self, message: Message, addr) -> Message:
        sender_id = message.sender_id
        trusted_key = self.trusted_keys.get(sender_id)

        task_bytes = bytes.fromhex(message.payload["task"])
        signature = bytes.fromhex(message.payload["signature"])

        if trusted_key is None:
            logger.warning("Rejected task from untrusted node_id=%s (no known public key)", sender_id)
            return Message(SECURE_TASK_RESULT, self.node.node_id,
                            payload={"status": "rejected", "reason": "sender not trusted"},
                            msg_id=message.msg_id)

        if not verify_signature(trusted_key, task_bytes, signature):
            logger.warning("Rejected task from %s: signature verification FAILED", sender_id)
            return Message(SECURE_TASK_RESULT, self.node.node_id,
                            payload={"status": "rejected", "reason": "invalid signature"},
                            msg_id=message.msg_id)

        try:
            func, args, kwargs = deserialize_task(task_bytes)
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            import cloudpickle
            return Message(SECURE_TASK_RESULT, self.node.node_id,
                            payload={"status": "ok", "result": cloudpickle.dumps(result).hex()},
                            msg_id=message.msg_id)
        except Exception as e:
            return Message(SECURE_TASK_RESULT, self.node.node_id,
                            payload={"status": "error", "error": str(e)},
                            msg_id=message.msg_id)


if __name__ == "__main__":
    def add(a, b):
        return a + b

    async def _demo():
        node_a = await SecureNode("node-A", port=9501).start()
        node_b = await SecureNode("node-B", port=9502).start()

        priv_a, pub_a = generate_signing_keypair()
        priv_b, pub_b = generate_signing_keypair()

        exec_a = SecureExecutor(node_a, priv_a)
        exec_b = SecureExecutor(node_b, priv_b)

        # Nodes must explicitly trust each other's public key before
        # they'll accept tasks from one another.
        exec_b.trust_peer(node_a.node_id, pub_a)

        print("Sending TLS-encrypted, signed task from A to B (B trusts A)...")
        result = await exec_a.submit_task(node_b.host, node_b.port, add, 4, 5)
        print(f"  -> Result: {result}")

        print("\nSimulating an impostor: a node pretending to be node-A, but")
        print("signing with the WRONG private key...")
        fake_priv, _ = generate_signing_keypair()
        impostor = SecureExecutor(node_a, fake_priv)  # reuses node_a's transport, wrong key
        # Force sender_id to claim it's "node-A" while signing with fake_priv
        impostor.node = node_a
        try:
            task_bytes = serialize_task(add, 1, 1)
            bad_sig = sign_bytes(fake_priv, task_bytes)
            forged = Message(SECURE_TASK_SUBMIT, "node-A",
                              payload={"task": task_bytes.hex(), "signature": bad_sig.hex()})
            reply = await node_a.send_tcp(node_b.host, node_b.port, forged)
            print(f"  -> Node-B response: {reply.payload}")
        except Exception as e:
            print(f"  -> Rejected as expected: {e}")

        await node_a.stop()
        await node_b.stop()
        print("\nNodes shut down cleanly.")

    asyncio.run(_demo())
