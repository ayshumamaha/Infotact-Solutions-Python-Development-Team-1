"""
async_networking.py
--------------------
Module 1 of MeshWeaver: Async Networking.

Provides a `Node` class that can:
  - Listen for UDP and TCP traffic without blocking (asyncio).
  - Send UDP datagrams (fire-and-forget) and TCP messages (reliable).
  - Ping another node and await a Pong, with a timeout.
  - Register custom message handlers, so later modules (Gossip, Task
    Routing, Remote Execution) can plug in new message types without
    touching this file.

Wire format: every message is a single JSON object, UTF-8 encoded.
  UDP:  {"type": "PING", "msg_id": "...", "sender_id": "...", "payload": {...}}
  TCP:  length-prefixed JSON (4-byte big-endian length header + JSON body),
        because TCP is a byte stream and has no built-in message boundaries.
"""

import asyncio
import json
import struct
import uuid
import time
import logging

logger = logging.getLogger("meshweaver.async_networking")


class Message:
    """A single wire message."""

    def __init__(self, msg_type: str, sender_id: str, payload: dict = None, msg_id: str = None):
        self.type = msg_type
        self.sender_id = sender_id
        self.payload = payload or {}
        self.msg_id = msg_id or str(uuid.uuid4())
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "sender_id": self.sender_id,
            "payload": self.payload,
            "msg_id": self.msg_id,
            "timestamp": self.timestamp,
        }

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_dict()).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        d = json.loads(data.decode("utf-8"))
        msg = cls(d["type"], d["sender_id"], d.get("payload", {}), d.get("msg_id"))
        msg.timestamp = d.get("timestamp", time.time())
        return msg


class _UDPProtocol(asyncio.DatagramProtocol):
    """Low-level asyncio protocol that hands datagrams to the owning Node."""

    def __init__(self, node: "Node"):
        self.node = node

    def datagram_received(self, data: bytes, addr):
        self.node._handle_incoming(data, addr, transport="udp")

    def error_received(self, exc):
        logger.warning("UDP error: %s", exc)


class Node:
    """
    A single MeshWeaver peer. Owns a UDP listener and a TCP listener,
    and exposes send/ping primitives on top of them.
    """

    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 0):
        self.node_id = node_id
        self.host = host
        self.port = port  # 0 = let the OS pick a free port; set after start()

        self._udp_transport = None
        self._tcp_server = None
        self._handlers = {}          # msg_type -> async callback(message, addr)
        self._pending_pings = {}     # msg_id -> asyncio.Future

        # Built-in handlers every node supports out of the box.
        self.register_handler("PING", self._on_ping)
        self.register_handler("PONG", self._on_pong)

    # ---------- lifecycle ----------

    async def start(self):
        """Start both the UDP and TCP listeners."""
        loop = asyncio.get_running_loop()

        transport, _ = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self),
            local_addr=(self.host, self.port),
        )
        self._udp_transport = transport
        # If port was 0, find out what the OS actually assigned.
        self.port = transport.get_extra_info("sockname")[1]

        self._tcp_server = await asyncio.start_server(
            self._handle_tcp_connection, host=self.host, port=self.port
        )

        logger.info("Node %s listening on %s:%s (UDP+TCP)", self.node_id, self.host, self.port)
        return self

    async def stop(self):
        """Shut down listeners cleanly."""
        if self._udp_transport:
            self._udp_transport.close()
        if self._tcp_server:
            self._tcp_server.close()
            await self._tcp_server.wait_closed()

    # ---------- handler registry ----------

    def register_handler(self, msg_type: str, callback):
        """
        Register an async callback for a message type.
        callback signature: async def callback(message: Message, addr) -> Optional[Message]
        If the callback returns a Message, it is sent back to the sender (TCP only).
        """
        self._handlers[msg_type] = callback

    # ---------- sending ----------

    def send_udp(self, host: str, port: int, message: Message):
        """Fire-and-forget send. Does not wait for any response."""
        self._udp_transport.sendto(message.to_bytes(), (host, port))

    async def send_tcp(self, host: str, port: int, message: Message, wait_response: bool = True, timeout: float = 5.0):
        """
        Reliable send over TCP. Optionally waits for a single response message.
        Used later by Remote Task Execution to ship serialized tasks.
        """
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
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

    async def ping(self, host: str, port: int, timeout: float = 2.0) -> float:
        """
        Ping another node over UDP and wait for its Pong.
        Returns round-trip time in seconds. Raises asyncio.TimeoutError if no reply.
        """
        msg = Message("PING", self.node_id)
        fut = asyncio.get_running_loop().create_future()
        self._pending_pings[msg.msg_id] = fut

        start = time.monotonic()
        self.send_udp(host, port, msg)

        try:
            await asyncio.wait_for(fut, timeout=timeout)
            return time.monotonic() - start
        finally:
            self._pending_pings.pop(msg.msg_id, None)

    # ---------- incoming traffic ----------

    def _handle_incoming(self, data: bytes, addr, transport: str):
        try:
            message = Message.from_bytes(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Dropping malformed %s message from %s: %s", transport, addr, e)
            return
        asyncio.ensure_future(self._dispatch(message, addr))

    async def _dispatch(self, message: Message, addr):
        handler = self._handlers.get(message.type)
        if handler is None:
            logger.debug("No handler for message type %s", message.type)
            return
        await handler(message, addr)

    async def _handle_tcp_connection(self, reader, writer):
        addr = writer.get_extra_info("peername")
        try:
            data = await _read_framed(reader)
            if not data:
                return
            message = Message.from_bytes(data)
            handler = self._handlers.get(message.type)
            reply = await handler(message, addr) if handler else None
            if reply is not None:
                _write_framed(writer, reply.to_bytes())
                await writer.drain()
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Dropping malformed TCP message from %s: %s", addr, e)
        finally:
            writer.close()
            await writer.wait_closed()

    # ---------- built-in handlers ----------

    async def _on_ping(self, message: Message, addr):
        pong = Message("PONG", self.node_id, msg_id=message.msg_id)
        self.send_udp(addr[0], addr[1], pong)

    async def _on_pong(self, message: Message, addr):
        fut = self._pending_pings.get(message.msg_id)
        if fut and not fut.done():
            fut.set_result(True)


# ---------- TCP framing helpers ----------

def _write_framed(writer: asyncio.StreamWriter, data: bytes):
    writer.write(struct.pack(">I", len(data)) + data)


async def _read_framed(reader: asyncio.StreamReader):
    header = await reader.readexactly(4)
    (length,) = struct.unpack(">I", header)
    return await reader.readexactly(length)


if __name__ == "__main__":
    # Quick self-test: start two nodes and ping between them.
    async def _demo():
        node_a = await Node("node-A", port=9001).start()
        node_b = await Node("node-B", port=9002).start()

        print(f"node-A listening on {node_a.host}:{node_a.port}")
        print(f"node-B listening on {node_b.host}:{node_b.port}")

        rtt = await node_a.ping(node_b.host, node_b.port)
        print(f"node-A pinged node-B -> Pong received! RTT = {rtt*1000:.2f} ms")

        rtt = await node_b.ping(node_a.host, node_a.port)
        print(f"node-B pinged node-A -> Pong received! RTT = {rtt*1000:.2f} ms")

        await node_a.stop()
        await node_b.stop()
        print("Nodes shut down cleanly.")

    asyncio.run(_demo())
