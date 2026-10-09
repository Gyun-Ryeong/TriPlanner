package com.triplanner.backend.common;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Supplier;

// 외부 API 호출 결과를 잠깐 들고 있는 단순 캐시 (로딩에 실패하면 예외가 그대로 올라가고 아무것도 저장하지 않는다)
public class TtlCache<K, V> {

    private record Entry<V>(V value, long expiresAtMillis) {
    }

    private final Map<K, Entry<V>> entries = new ConcurrentHashMap<>();
    private final long ttlMillis;

    public TtlCache(Duration ttl) {
        this.ttlMillis = ttl.toMillis();
    }

    // 유효한 캐시 값이 있으면 돌려주고 없으면 null (일부만 성공한 결과를 저장하지 않으려고 get 대신 쓴다)
    public V getIfPresent(K key) {
        Entry<V> cached = entries.get(key);
        return cached != null && cached.expiresAtMillis() > System.currentTimeMillis() ? cached.value() : null;
    }

    public void put(K key, V value) {
        entries.put(key, new Entry<>(value, System.currentTimeMillis() + ttlMillis));
    }

    public V get(K key, Supplier<V> loader) {
        long now = System.currentTimeMillis();
        Entry<V> cached = entries.get(key);
        if (cached != null && cached.expiresAtMillis() > now) {
            return cached.value();
        }

        V loaded = loader.get();
        entries.put(key, new Entry<>(loaded, now + ttlMillis));
        return loaded;
    }
}
