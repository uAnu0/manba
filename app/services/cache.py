"""A small in-memory cache for the async model calls: the same claim, question or text costs nothing the second time.

Entries live as long as the server process (and expire after `ttl` seconds). Failures are never cached. The API key is
not part of the cache key: the answer does not depend on whose key paid for it.
"""
import copy
import functools
import inspect
import json
import time
from collections import OrderedDict


def async_cache(maxsize: int = 512, ttl: float = 6 * 3600):
    def decorator(fn):
        store: OrderedDict[str, tuple[float, object]] = OrderedDict()
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            key = json.dumps(
                sorted((name, value) for name, value in bound.arguments.items() if name != "api_key"),
                ensure_ascii=False,
                default=repr,
            )
            hit = store.get(key)
            if hit is not None and time.time() - hit[0] < ttl:
                store.move_to_end(key)
                return copy.deepcopy(hit[1])
            result = await fn(*args, **kwargs)
            store[key] = (time.time(), copy.deepcopy(result))
            if len(store) > maxsize:
                store.popitem(last=False)
            return result

        wrapper.cache_clear = store.clear  # type: ignore[attr-defined]
        return wrapper

    return decorator
