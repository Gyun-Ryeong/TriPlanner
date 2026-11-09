package com.triplanner.backend.service;

import com.triplanner.backend.common.TtlCache;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.util.HtmlUtils;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

// 네이버 뉴스 검색(NAVER API HUB). 장소 검색(PlaceService)과 같은 HUB 앱 키(naver.app)를 쓰며, 앱에 '뉴스' API 가 선택되어 있어야 한다.
// 축제 달력에서 '얼마나 많이 다뤄졌나'(검색 결과 총 건수)와 '관련 기사 한 건'을 볼 때만 쓴다
@Component
public class NaverNewsClient {

    public record NewsItem(String title, String description, String link, String pubDate) {
    }

    private static final Pattern TAG = Pattern.compile("<[^>]+>");
    // 짧은 시간에 호출이 몰리면 429(호출 과다)가 나므로 호출 사이에 최소 간격을 둔다 (초당 약 8회 이하)
    private static final long MIN_INTERVAL_MILLIS = 120;
    // 호출이 실패하면 이 시간 동안은 바로 실패로 처리해, 한 달 목록을 만드는 중에 느린 서버를 수십 번 기다리지 않게 한다
    private static final long COOLDOWN_MILLIS = 120_000;

    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final String clientId;
    private final String clientSecret;
    private final TtlCache<String, Long> totals = new TtlCache<>(Duration.ofHours(24));
    private long lastCallMillis = 0;
    private volatile long downUntilMillis = 0;

    public NaverNewsClient(
            ObjectMapper objectMapper,
            @Value("${naver.app.client-id}") String clientId,
            @Value("${naver.app.client-secret}") String clientSecret
    ) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Duration.ofSeconds(3));
        requestFactory.setReadTimeout(Duration.ofSeconds(10));
        this.restClient = RestClient.builder().requestFactory(requestFactory).build();
        this.objectMapper = objectMapper;
        this.clientId = clientId;
        this.clientSecret = clientSecret;
    }

    // 검색 결과 전체 건수. 실패하면 예외 (호출한 쪽이 '모름'으로 처리한다)
    public long total(String query) {
        Long cached = totals.getIfPresent(query);
        if (cached != null) {
            return cached;
        }
        long total = fetch(query, 1, "sim").path("total").asLong(0);
        totals.put(query, total);
        return total;
    }

    // 최신순 기사. 실패하면 예외
    public List<NewsItem> latest(String query, int display) {
        List<NewsItem> out = new ArrayList<>();
        for (JsonNode item : fetch(query, display, "date").path("items")) {
            String link = item.path("originallink").asString("");
            out.add(new NewsItem(
                    clean(item.path("title").asString("")),
                    clean(item.path("description").asString("")),
                    link.isEmpty() ? item.path("link").asString("") : link,
                    item.path("pubDate").asString("")));
        }
        return out;
    }

    private JsonNode fetch(String query, int display, String sort) {
        if (System.currentTimeMillis() < downUntilMillis) {
            throw new IllegalStateException("뉴스 검색이 직전에 실패해 잠시 쉬는 중입니다");
        }
        try {
            String body = null;
            for (int attempt = 0; attempt < 3; attempt++) {
                throttle();
                try {
                    body = restClient.get()
                            .uri(b -> b.scheme("https").host("naverapihub.apigw.ntruss.com").path("/search/v1/news")
                                    .queryParam("query", "{query}").queryParam("display", display)
                                    .queryParam("sort", sort).build(query))
                            .header("X-NCP-APIGW-API-KEY-ID", clientId)
                            .header("X-NCP-APIGW-API-KEY", clientSecret)
                            .retrieve()
                            .body(String.class);
                    break;
                } catch (HttpClientErrorException.TooManyRequests e) {
                    if (attempt == 2) {
                        throw e;
                    }
                    Thread.sleep(1000L * (attempt + 1));
                }
            }
            // HUB 는 JSON 을 text/plain 으로 내려주므로 직접 파싱한다
            return objectMapper.readTree(body == null ? "{}" : body);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("뉴스 검색이 중단되었습니다");
        } catch (HttpClientErrorException.BadRequest e) {
            throw e; // 검색어 하나가 잘못된 것이므로 다른 검색까지 쉬게 하지 않는다
        } catch (RuntimeException e) {
            downUntilMillis = System.currentTimeMillis() + COOLDOWN_MILLIS;
            throw e;
        }
    }

    private synchronized void throttle() throws InterruptedException {
        long wait = MIN_INTERVAL_MILLIS - (System.currentTimeMillis() - lastCallMillis);
        if (wait > 0) {
            Thread.sleep(wait);
        }
        lastCallMillis = System.currentTimeMillis();
    }

    // 제목·요약에는 검색어 강조용 <b> 태그와 HTML 엔티티가 섞여 온다
    static String clean(String text) {
        return TAG.matcher(HtmlUtils.htmlUnescape(text == null ? "" : text)).replaceAll("").trim();
    }
}
