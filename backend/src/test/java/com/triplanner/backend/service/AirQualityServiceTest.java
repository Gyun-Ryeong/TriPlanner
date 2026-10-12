package com.triplanner.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.triplanner.backend.dto.RegionAirQualityResponse;
import com.triplanner.backend.dto.RegionAirQualityResponse.AreaAirQuality;
import com.triplanner.backend.dto.RegionAirQualityResponse.Metric;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.server.ResponseStatusException;

class AirQualityServiceTest {

    // 에어코리아를 실제로 부르지 않고, 시도별 응답을 테스트가 정한다
    private static class FakeAirQualityService extends AirQualityService {
        final AtomicInteger calls = new AtomicInteger();
        Function<String, AreaAirQuality> behavior;

        @Override
        AreaAirQuality fetchAreaAirQuality(String sidoName) {
            calls.incrementAndGet();
            return behavior.apply(sidoName);
        }
    }

    private static AreaAirQuality area(String sido) {
        Metric metric = new Metric(20.0, "좋음", null);
        return new AreaAirQuality(sido, "2026-10-12 16:00", metric, metric, metric, metric);
    }

    private static FakeAirQualityService service(Function<String, AreaAirQuality> behavior) {
        FakeAirQualityService service = new FakeAirQualityService();
        service.behavior = behavior;
        return service;
    }

    @Test
    void successfulResultIsCachedAndNotFetchedAgain() {
        FakeAirQualityService service = service(AirQualityServiceTest::area);

        List<RegionAirQualityResponse> first = service.getRegionAirQuality();
        int callsAfterFirst = service.calls.get();
        List<RegionAirQualityResponse> second = service.getRegionAirQuality();

        assertEquals(7, first.size());
        assertEquals(17, callsAfterFirst);
        assertSame(first, second);
        assertEquals(callsAfterFirst, service.calls.get());
    }

    @Test
    void dailyQuotaStopsRetriesAndFurtherCalls() {
        FakeAirQualityService service = service(sido -> {
            throw new AirQualityService.QuotaExceededException(true);
        });

        ResponseStatusException first = assertThrows(ResponseStatusException.class, service::getRegionAirQuality);
        int callsAfterFirst = service.calls.get();
        ResponseStatusException second = assertThrows(ResponseStatusException.class, service::getRegionAirQuality);

        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, first.getStatusCode());
        assertTrue(first.getReason().contains("한도"));
        // 시도마다 한 번씩만 불렀고(재시도 없음), 두 번째 요청은 에어코리아를 전혀 부르지 않았다
        assertEquals(17, callsAfterFirst);
        assertEquals(callsAfterFirst, service.calls.get());
        assertEquals(first.getReason(), second.getReason());
    }

    @Test
    void shortQuotaUsesDifferentMessage() {
        FakeAirQualityService service = service(sido -> {
            throw new AirQualityService.QuotaExceededException(false);
        });

        ResponseStatusException error = assertThrows(ResponseStatusException.class, service::getRegionAirQuality);

        assertTrue(error.getReason().contains("잠시"));
    }

    @Test
    void lastCompleteResultIsServedWhileBlocked() {
        FakeAirQualityService service = service(sido -> {
            throw new AirQualityService.QuotaExceededException(true);
        });
        List<RegionAirQualityResponse> stale = List.of();
        ReflectionTestUtils.setField(service, "lastComplete", stale);

        assertSame(stale, service.getRegionAirQuality());
        int callsAfterFirst = service.calls.get();
        assertSame(stale, service.getRegionAirQuality());
        assertEquals(callsAfterFirst, service.calls.get());
    }

    @Test
    void ordinaryFailureIsRetriedOnceButDoesNotBlock() {
        FakeAirQualityService service = service(sido -> null);

        ResponseStatusException first = assertThrows(ResponseStatusException.class, service::getRegionAirQuality);
        int callsAfterFirst = service.calls.get();
        assertThrows(ResponseStatusException.class, service::getRegionAirQuality);

        assertEquals(HttpStatus.BAD_GATEWAY, first.getStatusCode());
        assertEquals(34, callsAfterFirst);
        assertEquals(68, service.calls.get());
    }

    @Test
    void partialResultIsCachedBriefly() {
        FakeAirQualityService service = service(sido -> "제주".equals(sido) ? null : area(sido));

        List<RegionAirQualityResponse> first = service.getRegionAirQuality();
        int callsAfterFirst = service.calls.get();
        List<RegionAirQualityResponse> second = service.getRegionAirQuality();

        // 제주 한 곳이 빠져 6개 권역만 온다
        assertEquals(6, first.size());
        assertSame(first, second);
        assertEquals(callsAfterFirst, service.calls.get());
    }
}
