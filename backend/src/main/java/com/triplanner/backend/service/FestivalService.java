package com.triplanner.backend.service;

import com.triplanner.backend.common.TtlCache;
import com.triplanner.backend.dto.FestivalCalendarResponse;
import com.triplanner.backend.dto.FestivalDetailResponse;
import com.triplanner.backend.dto.FestivalLink;
import com.triplanner.backend.dto.FestivalSummary;
import com.triplanner.backend.service.NaverNewsClient.NewsItem;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDate;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.OptionalLong;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.util.HtmlUtils;
import tools.jackson.databind.JsonNode;

// 축제 달력: 한국관광공사 TourAPI 에서 월별 축제를 모으고, 같은 날 겹치는 축제는 네이버 뉴스 건수가 많은 쪽을 대표로 세운다.
// 월 목록은 같은 시도·같은 달을 여러 사람이 볼 수 있어 1시간, 상세는 6시간 기억한다 (실패한 결과는 기억하지 않는다)
@Service
public class FestivalService {

    private static final Logger log = LoggerFactory.getLogger(FestivalService.class);

    private static final int MAX_DAYS = 120;          // 이보다 길게 이어지는 '축제'는 잘못 들어간 자료로 보고 뺀다
    private static final int MAX_NEWS_LOOKUPS = 60;   // 한 번의 조회에서 뉴스 건수를 확인하는 축제 수 상한 (호출 한도 보호)
    private static final int NEWS_LINK_DAYS = 90;     // 관련 뉴스 링크는 최근 3개월 기사까지

    // 시도 표준 이름 → 다른 표기. 법정동 코드는 행정구역 개편으로 바뀔 수 있어 TourAPI 응답에서 이름으로 찾는다
    private static final Map<String, List<String>> SIDO = new LinkedHashMap<>();

    static {
        SIDO.put("서울", List.of("서울특별시", "서울시"));
        SIDO.put("부산", List.of("부산광역시", "부산시"));
        SIDO.put("대구", List.of("대구광역시", "대구시"));
        SIDO.put("인천", List.of("인천광역시", "인천시"));
        SIDO.put("광주", List.of("광주광역시"));
        SIDO.put("대전", List.of("대전광역시", "대전시"));
        SIDO.put("울산", List.of("울산광역시", "울산시"));
        SIDO.put("세종", List.of("세종특별자치시", "세종시"));
        SIDO.put("경기", List.of("경기도"));
        SIDO.put("강원", List.of("강원도", "강원특별자치도"));
        SIDO.put("충북", List.of("충청북도"));
        SIDO.put("충남", List.of("충청남도"));
        SIDO.put("전북", List.of("전라북도", "전북특별자치도"));
        SIDO.put("전남", List.of("전라남도"));
        SIDO.put("경북", List.of("경상북도"));
        SIDO.put("경남", List.of("경상남도"));
        SIDO.put("제주", List.of("제주도", "제주특별자치도"));
    }

    private static final Pattern YEAR = Pattern.compile("\\b(19|20)\\d{2}\\b");
    private static final Pattern BRACKETS = Pattern.compile("\\s*[\\[(（].*?[\\])）]\\s*");
    private static final Pattern QUOTES = Pattern.compile("[《》〈〉「」『』“”\"'‘’]");
    private static final Pattern TAGS = Pattern.compile("<[^>]+>");
    private static final Pattern HREF = Pattern.compile("href\\s*=\\s*[\"']([^\"']+)[\"']", Pattern.CASE_INSENSITIVE);
    private static final Pattern URL = Pattern.compile("https?://[^\\s\"'<>]+", Pattern.CASE_INSENSITIVE);
    private static final Pattern BARE_DOMAIN = Pattern.compile("[\\p{L}\\p{N}_-]+(\\.[\\p{L}\\p{N}_-]+)+(/.*)?");

    private final TourApiClient tourApi;
    private final NaverNewsClient news;
    private final TtlCache<String, FestivalCalendarResponse> months = new TtlCache<>(Duration.ofHours(1));
    private final TtlCache<String, FestivalDetailResponse> details = new TtlCache<>(Duration.ofHours(6));

    public FestivalService(TourApiClient tourApi, NaverNewsClient news) {
        this.tourApi = tourApi;
        this.news = news;
    }

    // ── 월 목록 ────────────────────────────────────────────────────────
    public FestivalCalendarResponse getMonth(String sido, int year, int month) {
        String name = normalizeSido(sido);
        if (name == null || year < 2000 || year > 2100 || month < 1 || month > 12) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "지원하지 않는 지역이거나 날짜가 올바르지 않습니다.");
        }
        String key = name + "|" + year + "|" + month;
        FestivalCalendarResponse cached = months.getIfPresent(key);
        if (cached != null) {
            return cached;
        }
        try {
            FestivalCalendarResponse built = buildMonth(name, year, month);
            months.put(key, built);
            return built;
        } catch (RuntimeException e) {
            // 공공 API 장애·한도 초과: '축제가 없다'가 아니라 '불러오지 못했다'로 알려 화면이 안내할 수 있게 한다
            log.warn("축제 목록 조회 실패 sido={} cause={} {}", name, e.getClass().getSimpleName(), e.getMessage());
            return FestivalCalendarResponse.unavailable(name, year, month);
        }
    }

    static String normalizeSido(String text) {
        String t = text == null ? "" : text.trim();
        if (t.isEmpty() || t.length() > 20) {
            return null;
        }
        if (SIDO.containsKey(t)) {
            return t;
        }
        for (Map.Entry<String, List<String>> e : SIDO.entrySet()) {
            if (e.getValue().contains(t)) {
                return e.getKey();
            }
        }
        return null;
    }

    // 시도 이름으로 TourAPI 법정동 코드와, 여러 시도가 같은 코드를 쓰는지(광주·전남 통합 등)를 찾는다
    record Region(String code, boolean shared) {
    }

    Region resolveRegion(String sido) {
        Map<String, String> mapping = tourApi.regionCodes();
        String code = matchRegion(mapping, sido);
        if (code == null) {
            throw new TourApiClient.TourApiException("시도 코드를 찾지 못했습니다: " + sido);
        }
        long sharing = SIDO.keySet().stream().filter(s -> code.equals(matchRegion(mapping, s))).count();
        return new Region(code, sharing > 1);
    }

    private static String matchRegion(Map<String, String> mapping, String sido) {
        List<String> tokens = new ArrayList<>();
        tokens.add(sido);
        tokens.addAll(SIDO.get(sido));
        for (Map.Entry<String, String> e : mapping.entrySet()) {
            for (String token : tokens) {
                if (e.getKey().contains(token) || token.contains(e.getKey())) {
                    return e.getValue();
                }
            }
        }
        return null;
    }

    record Festival(String contentId, String title, String addr, LocalDate start, LocalDate end,
                            String image, String mapx, String mapy) {
        long span() {
            return ChronoUnit.DAYS.between(start, end);
        }

        FestivalSummary toSummary() {
            return new FestivalSummary(contentId, title, addr, start.toString(), end.toString(), image, mapx, mapy);
        }
    }

    FestivalCalendarResponse buildMonth(String sido, int year, int month) {
        Region region = resolveRegion(sido);
        LocalDate first = LocalDate.of(year, month, 1);
        LocalDate last = first.withDayOfMonth(first.lengthOfMonth());

        Map<String, Festival> seen = new LinkedHashMap<>();
        for (JsonNode item : tourApi.festivals(region.code(), year, month)) {
            Festival f = toFestival(item);
            if (f == null || f.contentId().isEmpty() || seen.containsKey(f.contentId())) {
                continue;
            }
            if (region.shared() && !inSido(f.addr(), sido)) {
                continue; // 광주·전남처럼 시도 코드를 같이 쓰면 주소로 한 번 더 거른다
            }
            if (!daysOf(f, first, last).isEmpty()) {
                seen.put(f.contentId(), f);
            }
        }
        List<Festival> festivals = new ArrayList<>(seen.values());

        Map<LocalDate, List<Festival>> byDay = new TreeMap<>();
        for (Festival f : festivals) {
            for (LocalDate d : daysOf(f, first, last)) {
                byDay.computeIfAbsent(d, k -> new ArrayList<>()).add(f);
            }
        }

        // 같은 날 겹치는 축제만 뉴스 건수로 순위를 가린다 (상한을 넘으면 나머지는 기간 순)
        Map<String, Festival> contested = new LinkedHashMap<>();
        byDay.values().stream().filter(list -> list.size() > 1).forEach(list -> list.forEach(f -> contested.put(f.contentId(), f)));
        Map<String, Long> newsCounts = new HashMap<>();
        contested.values().stream()
                .sorted(Comparator.comparing(Festival::start).thenComparing(Festival::end))
                .limit(MAX_NEWS_LOOKUPS)
                .forEach(f -> newsCount(f.title(), sido).ifPresent(n -> newsCounts.put(f.contentId(), n)));

        // 뉴스 건수 많은 순 → 기간 긴 순 → 이름 (항상 같은 결과가 나오게)
        Comparator<Festival> rank = Comparator
                .comparingLong((Festival f) -> -newsCounts.getOrDefault(f.contentId(), 0L))
                .thenComparingLong(f -> -f.span())
                .thenComparing(Festival::title);

        Map<String, List<String>> days = new LinkedHashMap<>();
        byDay.forEach((day, list) -> days.put(day.toString(), list.stream().sorted(rank).map(Festival::contentId).toList()));
        festivals.sort(Comparator.comparing(Festival::start).thenComparing(Festival::end).thenComparing(Festival::title));
        return new FestivalCalendarResponse(sido, year, month, festivals.stream().map(Festival::toSummary).toList(), days, true);
    }

    private static boolean inSido(String addr, String sido) {
        return addr.contains(sido) || SIDO.get(sido).stream().anyMatch(addr::contains);
    }

    // TourAPI 항목 → 달력용 축제. 날짜가 비었거나 비정상이면 null
    static Festival toFestival(JsonNode item) {
        LocalDate start = parseDate(item.path("eventstartdate").asString(""));
        LocalDate end = parseDate(item.path("eventenddate").asString(""));
        if (start == null || end == null || start.isAfter(end) || ChronoUnit.DAYS.between(start, end) > MAX_DAYS) {
            return null;
        }
        String addr = (item.path("addr1").asString("") + " " + item.path("addr2").asString("")).trim();
        return new Festival(
                item.path("contentid").asString("").trim(), item.path("title").asString("").trim(), addr, start, end,
                item.path("firstimage").asString("").replace("http://", "https://"),
                item.path("mapx").asString(""), item.path("mapy").asString(""));
    }

    static LocalDate parseDate(String yyyymmdd) {
        try {
            return LocalDate.parse(yyyymmdd == null ? "" : yyyymmdd.trim(), DateTimeFormatter.BASIC_ISO_DATE);
        } catch (DateTimeParseException e) {
            return null;
        }
    }

    private static List<LocalDate> daysOf(Festival f, LocalDate first, LocalDate last) {
        LocalDate s = f.start().isAfter(first) ? f.start() : first;
        LocalDate e = f.end().isBefore(last) ? f.end() : last;
        List<LocalDate> days = new ArrayList<>();
        for (LocalDate d = s; !d.isAfter(e); d = d.plusDays(1)) {
            days.add(d);
        }
        return days;
    }

    // 뉴스 검색어: 축제 이름 + 시도. 괄호·따옴표·연도는 빼야 해마다 같은 축제로 센다
    static String newsQuery(String title, String sido) {
        String t = BRACKETS.matcher(title).replaceAll(" ");
        t = QUOTES.matcher(t).replaceAll(" ");
        t = YEAR.matcher(t).replaceAll(" ");
        t = t.replaceAll("\\s+", " ").trim();
        return (t.isEmpty() ? title : t) + " " + sido;
    }

    private OptionalLong newsCount(String title, String sido) {
        try {
            return OptionalLong.of(news.total(newsQuery(title, sido)));
        } catch (RuntimeException e) {
            return OptionalLong.empty(); // 키 없음·한도·장애 → 기간 순으로 대신 정한다
        }
    }

    // ── 상세 ───────────────────────────────────────────────────────────
    // 축제 상세. 찾지 못하면 404, 공공 API 문제면 503
    public FestivalDetailResponse getDetail(String contentId) {
        String id = contentId == null ? "" : contentId.trim();
        if (id.isEmpty() || id.length() > 20 || !id.chars().allMatch(Character::isDigit)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "축제 번호가 올바르지 않습니다.");
        }
        FestivalDetailResponse cached = details.getIfPresent(id);
        if (cached != null) {
            return cached;
        }
        JsonNode common;
        try {
            common = tourApi.common(id);
        } catch (RuntimeException e) {
            log.warn("축제 상세 조회 실패 id={} cause={} {}", id, e.getClass().getSimpleName(), e.getMessage());
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "축제 정보를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.");
        }
        if (common == null || common.path("title").asString("").isBlank()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "축제 정보를 찾지 못했어요.");
        }
        JsonNode intro = null;
        try {
            intro = tourApi.intro(id);
        } catch (RuntimeException e) {
            log.warn("축제 소개 정보 조회 실패 id={} cause={}", id, e.getClass().getSimpleName()); // 기본 정보만 보여 준다
        }
        FestivalDetailResponse built = toDetail(id, common, intro);
        details.put(id, built);
        return built;
    }

    FestivalDetailResponse toDetail(String id, JsonNode common, JsonNode intro) {
        String title = common.path("title").asString("").trim();
        String addr = (common.path("addr1").asString("") + " " + common.path("addr2").asString("")).trim();
        String home = extractUrl(common.path("homepage").asString(""));

        // 링크 우선순위: ① 전용 홈페이지 → ② 관련 뉴스 → ③ 이름으로 검색(항상 가능). 시청 첫 화면 같은 홈페이지는 맨 뒤
        List<FestivalLink> links = new ArrayList<>();
        if (isDedicatedSite(home)) {
            links.add(new FestivalLink("homepage", "공식 홈페이지", home, ""));
        }
        FestivalLink newsLink = newsLink(title, sidoOf(addr));
        if (newsLink != null) {
            links.add(newsLink);
        }
        links.add(new FestivalLink("search", "네이버에서 검색", searchLink(title), ""));
        if (!home.isEmpty() && !isDedicatedSite(home)) {
            links.add(new FestivalLink("homepage_general", "관할 기관 홈페이지", home, ""));
        }

        LocalDate start = intro == null ? null : parseDate(intro.path("eventstartdate").asString(""));
        LocalDate end = intro == null ? null : parseDate(intro.path("eventenddate").asString(""));
        return new FestivalDetailResponse(
                id, title, addr,
                common.path("firstimage").asString("").replace("http://", "https://"),
                common.path("mapx").asString(""), common.path("mapy").asString(""),
                cleanText(common.path("tel").asString("")),
                cleanText(common.path("overview").asString("")),
                start == null ? "" : start.toString(), end == null ? "" : end.toString(),
                field(intro, "eventplace"), field(intro, "playtime"), field(intro, "usetimefestival"),
                field(intro, "program"),
                joinNonEmpty(field(intro, "sponsor1"), field(intro, "sponsor2")),
                links);
    }

    private static String field(JsonNode intro, String key) {
        return intro == null ? "" : cleanText(intro.path(key).asString(""));
    }

    private static String joinNonEmpty(String a, String b) {
        return a.isEmpty() ? b : (b.isEmpty() ? a : a + " · " + b);
    }

    // 태그를 걷어내고 HTML 엔티티를 풀고 공백을 한 칸으로 줄인다
    static String cleanText(String text) {
        String t = HtmlUtils.htmlUnescape(text == null ? "" : text);
        return TAGS.matcher(t).replaceAll(" ").replaceAll("\\s+", " ").trim();
    }

    // homepage 필드는 평문 URL 이거나 `<a href="...">` HTML 이다. 첫 번째 http(s) 주소만 꺼낸다
    static String extractUrl(String raw) {
        String text = HtmlUtils.htmlUnescape(raw == null ? "" : raw);
        Matcher href = HREF.matcher(text);
        Matcher url = URL.matcher(text);
        String cand;
        if (href.find()) {
            cand = href.group(1);
        } else if (url.find()) {
            cand = url.group();
        } else {
            cand = text.isBlank() ? "" : text.trim().split("\\s+")[0]; // 'www.festival.kr' 처럼 http 없이 적은 경우
        }
        cand = cand.trim().replaceAll("[.,)]+$", "");
        if (!cand.isEmpty() && !cand.regionMatches(true, 0, "http://", 0, 7) && !cand.regionMatches(true, 0, "https://", 0, 8)) {
            cand = BARE_DOMAIN.matcher(cand).matches() ? "https://" + cand : "";
        }
        return cand;
    }

    // 축제 전용 주소로 보이는가. 시청·군청 첫 화면(경로 없는 .go.kr)은 아니라고 본다
    static boolean isDedicatedSite(String url) {
        if (url == null || url.isEmpty()) {
            return false;
        }
        try {
            URI uri = URI.create(url);
            String host = uri.getHost() == null ? "" : uri.getHost();
            String path = uri.getPath() == null ? "" : uri.getPath().replaceAll("^/+|/+$", "");
            return !(host.endsWith(".go.kr") && path.isEmpty() && uri.getQuery() == null);
        } catch (IllegalArgumentException e) {
            return false;
        }
    }

    static String searchLink(String title) {
        return "https://search.naver.com/search.naver?query=" + URLEncoder.encode(title, StandardCharsets.UTF_8);
    }

    private static String sidoOf(String addr) {
        for (Map.Entry<String, List<String>> e : SIDO.entrySet()) {
            if (addr.startsWith(e.getKey()) || e.getValue().stream().anyMatch(addr::startsWith)) {
                return e.getKey();
            }
        }
        return "";
    }

    // 축제 이름이 모두 들어 있는 최근 기사 한 건 (제목에 이름이 있는 기사 → 최신 순). 못 찾거나 오류면 null
    private FestivalLink newsLink(String title, String sido) {
        try {
            String target = YEAR.matcher(title).replaceAll(" ").trim();
            NewsItem hit = pickFocus(news.latest(newsQuery(title, sido), 20), target.isEmpty() ? title : target, ZonedDateTime.now());
            return hit == null || hit.link().isEmpty() ? null : new FestivalLink("news", "관련 뉴스", hit.link(), hit.title());
        } catch (RuntimeException e) {
            return null;
        }
    }

    static NewsItem pickFocus(List<NewsItem> items, String target, ZonedDateTime now) {
        List<String> tokens = new ArrayList<>();
        for (String word : target.split("\\s+")) {
            String n = norm(word);
            if (!n.isEmpty()) {
                tokens.add(n);
            }
        }
        record Candidate(boolean inTitle, ZonedDateTime when, NewsItem item) {
        }
        List<Candidate> candidates = new ArrayList<>();
        for (NewsItem it : items) {
            ZonedDateTime when = publishedAt(it.pubDate());
            if (when == null || when.isBefore(now.minusDays(NEWS_LINK_DAYS))) {
                continue;
            }
            String titleNorm = norm(it.title());
            String body = norm(it.title() + it.description());
            if (tokens.stream().allMatch(body::contains)) {
                candidates.add(new Candidate(tokens.stream().allMatch(titleNorm::contains), when, it));
            }
        }
        return candidates.stream()
                .max(Comparator.comparing(Candidate::inTitle).thenComparing(Candidate::when))
                .map(Candidate::item).orElse(null);
    }

    private static String norm(String s) {
        return s == null ? "" : s.replaceAll("[^\\p{L}\\p{N}]+", "");
    }

    private static ZonedDateTime publishedAt(String pubDate) {
        try {
            return ZonedDateTime.parse(pubDate, DateTimeFormatter.RFC_1123_DATE_TIME);
        } catch (DateTimeParseException e) {
            return null;
        }
    }
}
