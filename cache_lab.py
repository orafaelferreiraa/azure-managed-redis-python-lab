import json
from typing import Any, Callable

import redis
from redis.crc import key_slot
from redis_entraid.cred_provider import create_from_default_azure_credential

REDIS_HOST = "reds.brazilsouth.redis.azure.net:10000"
CACHE_TTL_SECONDS = 30


class CacheLabClient:
    def __init__(self, host: str, port: int, credential_provider: Any) -> None:
        self.host = host
        self.port = port
        self.credential_provider = credential_provider
        self.startup_client = redis.Redis(
            host=host,
            port=port,
            ssl=True,
            decode_responses=True,
            credential_provider=credential_provider,
            socket_timeout=10,
            socket_connect_timeout=10,
        )
        self.node_clients: dict[int, redis.Redis] = {}
        self.slots = self._load_cluster_slots()

    def _load_cluster_slots(self) -> list[tuple[int, int, int]]:
        raw_slots = self.startup_client.execute_command("CLUSTER SLOTS")
        slot_ranges: list[tuple[int, int, int]] = []

        for slot in raw_slots:
            start_slot = int(slot[0])
            end_slot = int(slot[1])
            primary_port = int(slot[2][1])
            slot_ranges.append((start_slot, end_slot, primary_port))

        return slot_ranges

    def _get_port_for_key(self, key: str) -> int:
        slot = key_slot(key.encode("utf-8"))
        for start_slot, end_slot, port in self.slots:
            if start_slot <= slot <= end_slot:
                return port
        raise KeyError(f"No cluster slot mapping found for key '{key}'")

    def _get_node_client(self, key: str) -> redis.Redis:
        port = self._get_port_for_key(key)
        client = self.node_clients.get(port)
        if client is None:
            client = redis.Redis(
                host=self.host,
                port=port,
                ssl=True,
                decode_responses=True,
                credential_provider=self.credential_provider,
                socket_timeout=10,
                socket_connect_timeout=10,
            )
            self.node_clients[port] = client
        return client

    def ping(self) -> bool:
        return bool(self.startup_client.ping())

    def get(self, key: str) -> str | None:
        return self._get_node_client(key).get(key)

    def setex(self, key: str, ttl_seconds: int, value: str) -> bool:
        return bool(self._get_node_client(key).setex(key, ttl_seconds, value))

    def delete(self, key: str) -> int:
        return int(self._get_node_client(key).delete(key))

    def ttl(self, key: str) -> int:
        return int(self._get_node_client(key).ttl(key))

    def close(self) -> None:
        self.startup_client.close()
        for client in self.node_clients.values():
            client.close()


def create_client() -> CacheLabClient:
    host, port = REDIS_HOST.rsplit(":", 1)
    credential_provider = create_from_default_azure_credential(
        ("https://redis.azure.com/.default",),
    )
    return CacheLabClient(host, int(port), credential_provider)


def product_cache_key(product_id: int) -> str:
    return f"lab:product:{product_id}"


def read_cached_product(client: CacheLabClient, product_id: int) -> dict[str, Any] | None:
    cached = client.get(product_cache_key(product_id))
    if not cached:
        return None
    payload = json.loads(cached)
    payload["source"] = "redis-cache"
    return payload


def cache_product(client: CacheLabClient, product: dict[str, Any]) -> None:
    client.setex(
        product_cache_key(int(product["id"])),
        CACHE_TTL_SECONDS,
        json.dumps(product),
    )


def get_product_cache_aside(
    client: CacheLabClient,
    product_id: int,
    db_loader: Callable[[int], dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    cached = read_cached_product(client, product_id)
    if cached is not None:
        return cached, "cache-hit"

    product = db_loader(product_id)
    cache_product(client, product)
    product["source"] = "database"
    return product, "cache-miss"


def invalidate_product(client: CacheLabClient, product_id: int) -> int:
    return int(client.delete(product_cache_key(product_id)))


def get_product_ttl(client: CacheLabClient, product_id: int) -> int:
    return int(client.ttl(product_cache_key(product_id)))
