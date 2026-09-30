"""Offline guard: blocks every outbound network call inside the process.

Loopback (127.0.0.1 / ::1 / localhost) stays allowed so that the local REST API
(uvicorn on 127.0.0.1) and tests of it keep working.
"""
from __future__ import annotations

import contextlib
import os
import socket
from typing import Iterator

_ORIG = {
    "connect": socket.socket.connect,
    "connect_ex": socket.socket.connect_ex,
    "create_connection": socket.create_connection,
    "getaddrinfo": socket.getaddrinfo,
}
_LOOPBACK = {"127.0.0.1", "::1", "localhost", "0:0:0:0:0:0:0:1"}
_active = False

MESSAGE = ("Сетевой вызов запрещен (CHEM_AGENT_OFFLINE=1). Все данные должны быть локальными.")


class NetworkBlockedError(RuntimeError):
    pass


def _host_of(address) -> str | None:
    if isinstance(address, tuple) and address:
        return str(address[0])
    if isinstance(address, (str, bytes)):  # AF_UNIX path
        return "localhost"
    return None


def _check(host) -> None:
    if host is None:
        raise NetworkBlockedError(MESSAGE)
    h = host.decode() if isinstance(host, bytes) else str(host)
    if h not in _LOOPBACK:
        raise NetworkBlockedError(f"{MESSAGE} Адрес: {h}")


def _connect(self, address):
    _check(_host_of(address))
    return _ORIG["connect"](self, address)


def _connect_ex(self, address):
    _check(_host_of(address))
    return _ORIG["connect_ex"](self, address)


def _create_connection(address, *args, **kwargs):
    _check(_host_of(address))
    return _ORIG["create_connection"](address, *args, **kwargs)


def _getaddrinfo(host, *args, **kwargs):
    _check(host)
    return _ORIG["getaddrinfo"](host, *args, **kwargs)


def enable() -> None:
    global _active
    socket.socket.connect = _connect
    socket.socket.connect_ex = _connect_ex
    socket.create_connection = _create_connection
    socket.getaddrinfo = _getaddrinfo
    _active = True


def disable() -> None:
    global _active
    socket.socket.connect = _ORIG["connect"]
    socket.socket.connect_ex = _ORIG["connect_ex"]
    socket.create_connection = _ORIG["create_connection"]
    socket.getaddrinfo = _ORIG["getaddrinfo"]
    _active = False


def is_active() -> bool:
    return _active


@contextlib.contextmanager
def offline_guard() -> Iterator[None]:
    was = _active
    enable()
    try:
        yield
    finally:
        if not was:
            disable()


def assert_offline() -> None:
    if not _active:
        raise AssertionError("Офлайн-защита не включена (CHEM_AGENT_OFFLINE != 1)")


def enable_from_env() -> None:
    if os.environ.get("CHEM_AGENT_OFFLINE", "1") == "1":
        enable()
