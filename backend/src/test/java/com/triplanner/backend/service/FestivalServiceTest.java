package com.triplanner.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.triplanner.backend.dto.FestivalCalendarResponse;
import com.triplanner.backend.dto.FestivalDetailResponse;
import com.triplanner.backend.service.NaverNewsClient.NewsItem;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

class FestivalServiceTest {

    private final JsonMapper mapper = JsonMapper.builder().build();
    private TourApiClient tour;
    private NaverNewsClient news;
    private FestivalService service;

    @BeforeEach
    void setUp() {
        tour = mock(TourApiClient.class);
        news = mock(NaverNewsClient.class);
        service = new FestivalService(tour, news);
        // 실제 TourAPI 응답처럼 광주·전남이 한 코드(12)를 쓰고 세종은 5자리 코드다
        when(tour.regionCodes()).thenReturn(Map.of(
                "서울특별시", "11", "부산광역시", "26", "전남광주통합특별시", "12", "세종특별자치시", "36110"));
    }

    private JsonNode item(String id, String title, String start, String end, String addr) {
        return mapper.readTree("""
                {"contentid":"%s","title":"%s","eventstartdate":"%s","eventenddate":"%s",
                 "addr1":"%s","firstimage":"http://tong.visitkorea.or.kr/p.jpg","mapx":"129.1","mapy":"35.1"}
                """.formatted(id, title, start, end, addr));
    }

    private JsonNode item(String id, String title, String start, String end) {
        return item(id, title, start, end, "부산광역시 해운대구");
    }

    // ── 월 목록 ────────────────────────────────────────────────────────
    @Test
    void 같은_날_겹치면_뉴스_건수가_많은_축제가_대표가_된다() {
        when(tour.festivals("26", 2026, 11)).thenReturn(List.of(
                item("1", "A축제", "20261105", "20261107"), item("2", "B축제", "20261106", "20261106")));
        when(news.total(FestivalService.newsQuery("A축제", "부산"))).thenReturn(10L);
        when(news.total(FestivalService.newsQuery("B축제", "부산"))).thenReturn(300L);

        FestivalCalendarResponse r = service.getMonth("부산", 2026, 11);

        assertTrue(r.available());
        assertEquals(List.of("1"), r.days().get("2026-11-05"));        // 혼자인 날
        assertEquals(List.of("2", "1"), r.days().get("2026-11-06"));   // 겹치는 날: 뉴스 많은 B 가 맨 앞(대표)
        assertEquals(List.of("1"), r.days().get("2026-11-07"));
        assertTrue(r.festivals().get(0).image().startsWith("https://"));
    }

    @Test
    void 건수가_같거나_뉴스를_못_불러오면_기간이_긴_축제가_앞이다() {
        when(tour.festivals("26", 2026, 11)).thenReturn(List.of(
                item("1", "짧은축제", "20261110", "20261111"), item("2", "긴축제", "20261105", "20261120")));
        when(news.total(anyString())).thenThrow(new IllegalStateException("뉴스 키 없음"));

        FestivalCalendarResponse r = service.getMonth("부산", 2026, 11);

        assertEquals(List.of("2", "1"), r.days().get("2026-11-10"));
    }

    @Test
    void 겹치지_않으면_뉴스를_조회하지_않는다() {
        when(tour.festivals("26", 2026, 11)).thenReturn(List.of(
                item("1", "A", "20261101", "20261102"), item("2", "B", "20261103", "20261104")));

        service.getMonth("부산", 2026, 11);

        verify(news, never()).total(anyString());
    }

    @Test
    void 달에_걸친_축제는_그_달만큼만_채우고_이상한_자료는_뺀다() {
        when(tour.festivals("26", 2026, 11)).thenReturn(List.of(
                item("1", "이어지는축제", "20261025", "20261203"),
                item("2", "옛날자료", "20221101", "20261130"),     // 4년짜리 → 잘못 들어간 자료
                item("3", "거꾸로", "20261120", "20261110"),         // 시작이 끝보다 늦음
                item("4", "날짜없음", "", ""),
                item("1", "중복", "20261101", "20261102")));        // 같은 번호는 한 번만

        FestivalCalendarResponse r = service.getMonth("부산", 2026, 11);

        assertEquals(List.of("1"), r.festivals().stream().map(f -> f.contentId()).toList());
        assertEquals(30, r.days().size());                          // 11월 전체 30일
    }

    @Test
    void 시도_코드를_같이_쓰면_주소로_한_번_더_거른다() {
        when(tour.festivals("12", 2026, 11)).thenReturn(List.of(
                item("1", "광주 축제", "20261105", "20261106", "광주광역시 동구"),
                item("2", "전남 축제", "20261105", "20261106", "전라남도 여수시")));

        FestivalCalendarResponse r = service.getMonth("광주", 2026, 11);

        assertEquals(List.of("1"), r.festivals().stream().map(f -> f.contentId()).toList());
    }

    @Test
    void 세종은_TourAPI가_알려준_코드를_그대로_쓴다() {
        when(tour.festivals("36110", 2026, 11)).thenReturn(List.of(item("9", "세종축제", "20261105", "20261106", "세종특별자치시 조치원읍")));

        assertEquals(1, service.getMonth("세종특별자치시", 2026, 11).festivals().size());
    }

    @Test
    void 공공_API가_실패하면_없다가_아니라_불러오지_못함으로_응답하고_기억하지_않는다() {
        when(tour.festivals("26", 2026, 11)).thenThrow(new TourApiClient.TourApiException("한도 초과"));

        assertFalse(service.getMonth("부산", 2026, 11).available());

        doReturn(List.of(item("1", "A", "20261105", "20261105"))).when(tour).festivals("26", 2026, 11);
        assertTrue(service.getMonth("부산", 2026, 11).available()); // 실패는 저장되지 않아 다음 요청에서 다시 시도한다
    }

    @Test
    void 잘못된_입력은_400() {
        assertEquals(HttpStatus.BAD_REQUEST, assertThrows(ResponseStatusException.class, () -> service.getMonth("화성", 2026, 11)).getStatusCode());
        assertEquals(HttpStatus.BAD_REQUEST, assertThrows(ResponseStatusException.class, () -> service.getMonth("부산", 2026, 13)).getStatusCode());
        assertEquals(HttpStatus.BAD_REQUEST, assertThrows(ResponseStatusException.class, () -> service.getDetail("12; drop")).getStatusCode());
    }

    // ── 링크 ───────────────────────────────────────────────────────────
    @Test
    void homepage_필드에서_주소만_꺼낸다() {
        assertEquals("https://festival.example.kr/a", FestivalService.extractUrl("https://festival.example.kr/a"));
        assertEquals("http://x.kr/p?a=1&b=2", FestivalService.extractUrl("<a href=\"http://x.kr/p?a=1&amp;b=2\" target=\"_blank\">홈</a>"));
        assertEquals("https://www.festival.kr", FestivalService.extractUrl("www.festival.kr"));
        assertEquals("", FestivalService.extractUrl(""));
    }

    @Test
    void 시청_첫_화면은_전용_사이트가_아니다() {
        assertFalse(FestivalService.isDedicatedSite("https://www.goyang.go.kr/"));
        assertFalse(FestivalService.isDedicatedSite("https://www.goyang.go.kr"));
        assertTrue(FestivalService.isDedicatedSite("https://www.goyang.go.kr/flower/index.do"));
        assertTrue(FestivalService.isDedicatedSite("https://flowerfestival.kr"));
    }

    @Test
    void 관련_뉴스는_이름이_모두_들어간_최근_기사만_고른다() {
        ZonedDateTime now = ZonedDateTime.now();
        String recent = now.minusDays(2).format(DateTimeFormatter.RFC_1123_DATE_TIME);
        String old = now.minusDays(200).format(DateTimeFormatter.RFC_1123_DATE_TIME);
        List<NewsItem> items = List.of(
                new NewsItem("부산불꽃축제 안내", "", "https://old", old),
                new NewsItem("다른 소식", "부산불꽃축제가 언급됨", "https://body", recent),
                new NewsItem("부산 불꽃 축제 이번 주말", "", "https://title", recent),
                new NewsItem("전혀 다른 기사", "", "https://none", recent));

        assertEquals("https://title", FestivalService.pickFocus(items, "부산불꽃축제", now).link()); // 제목에 이름이 있는 기사
        assertNull(FestivalService.pickFocus(items, "없는축제", now));
    }

    // ── 상세 ───────────────────────────────────────────────────────────
    private JsonNode common(String homepage) {
        return mapper.readTree("""
                {"title":"부산불꽃축제","addr1":"부산광역시 수영구","homepage":"%s","tel":"051-713-5000",
                 "overview":"<p>가을 밤바다를 수놓는 불꽃</p>","firstimage":"http://x/y.jpg"}
                """.formatted(homepage));
    }

    private JsonNode intro() {
        return mapper.readTree("""
                {"eventstartdate":"20261107","eventenddate":"20261107","eventplace":"광안리","playtime":"19:00~20:00",
                 "program":"불꽃쇼","sponsor1":"부산시","sponsor2":""}
                """);
    }

    @Test
    void 상세_항목과_링크_순서_뉴스가_없을_때() {
        when(tour.common("123")).thenReturn(common("https://www.busan.go.kr/"));
        when(tour.intro("123")).thenReturn(intro());
        when(news.latest(anyString(), org.mockito.ArgumentMatchers.anyInt())).thenReturn(List.of());

        FestivalDetailResponse d = service.getDetail("123");

        assertEquals("19:00~20:00", d.playTime());
        assertEquals("광안리", d.place());
        assertEquals("부산시", d.sponsor());
        assertEquals("2026-11-07", d.start());
        assertEquals("가을 밤바다를 수놓는 불꽃", d.overview());
        assertEquals(List.of("search", "homepage_general"), d.links().stream().map(l -> l.kind()).toList()); // 시청 첫 화면은 맨 뒤
        assertTrue(d.links().get(0).url().contains("%EB%B6%80%EC%82%B0"));
    }

    @Test
    void 전용_홈페이지가_있으면_맨_앞이고_뉴스가_있으면_검색보다_앞이다() {
        when(tour.common("123")).thenReturn(common("https://fireworks.busan.kr"));
        when(tour.intro("123")).thenReturn(intro());
        String recent = ZonedDateTime.now().minusDays(1).format(DateTimeFormatter.RFC_1123_DATE_TIME);
        when(news.latest(anyString(), org.mockito.ArgumentMatchers.anyInt()))
                .thenReturn(List.of(new NewsItem("부산불꽃축제 이번 주말", "", "https://news.example/1", recent)));

        FestivalDetailResponse d = service.getDetail("123");

        assertEquals(List.of("homepage", "news", "search"), d.links().stream().map(l -> l.kind()).toList());
    }

    @Test
    void 소개_정보가_없어도_기본_정보는_보여_준다() {
        when(tour.common("123")).thenReturn(common(""));
        when(tour.intro("123")).thenThrow(new TourApiClient.TourApiException("down"));
        when(news.latest(anyString(), org.mockito.ArgumentMatchers.anyInt())).thenThrow(new IllegalStateException("no key"));

        FestivalDetailResponse d = service.getDetail("123");

        assertEquals("부산불꽃축제", d.title());
        assertEquals("", d.program());
        assertEquals("search", d.links().get(0).kind());
    }

    @Test
    void 상세는_없으면_404_공공_API가_실패하면_503() {
        when(tour.common("999")).thenReturn(null);
        assertEquals(HttpStatus.NOT_FOUND, assertThrows(ResponseStatusException.class, () -> service.getDetail("999")).getStatusCode());

        when(tour.common("500")).thenThrow(new TourApiClient.TourApiException("down"));
        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, assertThrows(ResponseStatusException.class, () -> service.getDetail("500")).getStatusCode());
    }
}
