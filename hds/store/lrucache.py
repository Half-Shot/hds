SENTINEL = object()

# Replace this with something non-licence infringing.
# Stolen from
# https://github.com/matrix-org/synapse/blob/d69decd5c78c72abef50b597a689e2bc55a39702/synapse/util/caches/lrucache.py

# -*- coding: utf-8 -*-
# Copyright 2015, 2016 OpenMarket Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


def enumerate_leaves(node, depth):
    if depth == 0:
        yield node
    else:
        for n in node.values():
            for m in enumerate_leaves(n, depth - 1):
                yield m


class _Node(object):
    __slots__ = ["prev_node", "next_node", "key", "value", "callbacks"]

    def __init__(self, prev_node, next_node, key, value, callbacks=set()):
        self.prev_node = prev_node
        self.next_node = next_node
        self.key = key
        self.value = value
        self.callbacks = callbacks


class LruCache(object):
    """
    Least-recently-used cache.
    Can also set callbacks on objects when getting/setting which are fired
    when that key gets invalidated/evicted.
    """
    def __init__(self, max_size, size_callback=None,
                 evicted_callback=None):
        """
        Args:
            max_size (int):
            size_callback (func(V) -> int | None):
            evicted_callback (func(int)|None):
                if not None, called on eviction with the size of the evicted
                entry
        """
        cache = dict()
        self.cache = cache  # Used for introspection.
        list_root = _Node(None, None, None, None)
        list_root.next_node = list_root
        list_root.prev_node = list_root

        def evict():
            while cache_len() > max_size:
                todelete = list_root.prev_node
                evicted_len = delete_node(todelete)
                cache.pop(todelete.key, None)
                if evicted_callback:
                    evicted_callback(evicted_len)

        cached_cache_len = [0]
        if size_callback is not None:
            def cache_len():
                return cached_cache_len[0]
        else:
            def cache_len():
                return len(cache)

        self.len = cache_len

        def add_node(key, value, callbacks=set()):
            prev_node = list_root
            next_node = prev_node.next_node
            node = _Node(prev_node, next_node, key, value, callbacks)
            prev_node.next_node = node
            next_node.prev_node = node
            cache[key] = node

            if size_callback:
                cached_cache_len[0] += size_callback(node.value)

        def move_node_to_front(node):
            prev_node = node.prev_node
            next_node = node.next_node
            prev_node.next_node = next_node
            next_node.prev_node = prev_node
            prev_node = list_root
            next_node = prev_node.next_node
            node.prev_node = prev_node
            node.next_node = next_node
            prev_node.next_node = node
            next_node.prev_node = node

        def delete_node(node):
            prev_node = node.prev_node
            next_node = node.next_node
            prev_node.next_node = next_node
            next_node.prev_node = prev_node

            deleted_len = 1
            if size_callback:
                deleted_len = size_callback(node.value)
                cached_cache_len[0] -= deleted_len

            for cb in node.callbacks:
                cb()
            node.callbacks.clear()
            return deleted_len

        def cache_get(key, default=None, callbacks=[]):
            node = cache.get(key, None)
            if node is not None:
                move_node_to_front(node)
                node.callbacks.update(callbacks)
                return node.value
            else:
                return default

        def cache_set(key, value, callbacks=[]):
            node = cache.get(key, None)
            if node is not None:
                # We sometimes store large objects, e.g. dicts, which cause
                # the inequality check to take a long time. So let's only do
                # the check if we have some callbacks to call.
                if node.callbacks and value != node.value:
                    for cb in node.callbacks:
                        cb()
                    node.callbacks.clear()

                # We don't bother to protect this by value != node.value as
                # generally size_callback will be cheap compared with equality
                # checks. (For example, taking the size of two dicts is quicker
                # than comparing them for equality.)
                if size_callback:
                    cached_cache_len[0] -= size_callback(node.value)
                    cached_cache_len[0] += size_callback(value)

                node.callbacks.update(callbacks)

                move_node_to_front(node)
                node.value = value
            else:
                add_node(key, value, set(callbacks))

            evict()

        def cache_set_default(key, value):
            node = cache.get(key, None)
            if node is not None:
                return node.value
            else:
                add_node(key, value)
                evict()
                return value

        def cache_pop(key, default=None):
            node = cache.get(key, None)
            if node:
                delete_node(node)
                cache.pop(node.key, None)
                return node.value
            else:
                return default

        def cache_clear():
            list_root.next_node = list_root
            list_root.prev_node = list_root
            for node in cache.values():
                for cb in node.callbacks:
                    cb()
            cache.clear()
            if size_callback:
                cached_cache_len[0] = 0

        def cache_contains(key):
            return key in cache

        self.sentinel = object()
        self.get = cache_get
        self.set = cache_set
        self.setdefault = cache_set_default
        self.pop = cache_pop
        self.len = cache_len
        self.contains = cache_contains
        self.clear = cache_clear

    def __getitem__(self, key):
        result = self.get(key, self.sentinel)
        if result is self.sentinel:
            raise KeyError()
        else:
            return result

    def __setitem__(self, key, value):
        self.set(key, value)

    def __delitem__(self, key):
        result = self.pop(key, self.sentinel)
        if result is self.sentinel:
            raise KeyError()

    def __len__(self):
        return self.len()

    def __contains__(self, key):
        return self.contains(key)
