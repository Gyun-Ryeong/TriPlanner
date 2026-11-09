package com.triplanner.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.triplanner.backend.service.TourApiClient.TourApiException;
import java.util.List;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

class TourApiClientTest {

    private final TourApiClient client = new TourApiClient(JsonMapper.builder().build(), "test-key");

    @Test
    void 정상_응답에서_항목_목록을_꺼낸다() {
        List<JsonNode> items = client.parseItems("searchFestival2", """
                {"response":{"header":{"resultCode":"0000","resultMsg":"OK"},
                 "body":{"items":{"item":[{"contentid":"1"},{"contentid":"2"}]},"totalCount":2}}}""");

        assertEquals(2, items.size());
        assertEquals("2", items.get(1).path("contentid").asString(""));
    }

    @Test
    void 항목이_하나면_배열이_아니라_객체로_온다() {
        List<JsonNode> items = client.parseItems("detailCommon2", """
                {"response":{"header":{"resultCode":"0000"},"body":{"items":{"item":{"contentid":"7"}}}}}""");

        assertEquals(1, items.size());
    }

    @Test
    void 결과가_없으면_items가_빈_문자열이어도_빈_목록() {
        assertTrue(client.parseItems("searchFestival2", """
                {"response":{"header":{"resultCode":"0000"},"body":{"items":"","totalCount":0}}}""").isEmpty());
    }

    @Test
    void 데이터_없음_코드도_오류가_아니라_빈_목록() {
        assertTrue(client.parseItems("searchFestival2", """
                {"response":{"header":{"resultCode":"03","resultMsg":"NODATA_ERROR"}}}""").isEmpty());
    }

    @Test
    void 인증키_오류_XML과_오류_코드는_예외() {
        assertThrows(TourApiException.class, () -> client.parseItems("searchFestival2",
                "<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg></cmmMsgHeader></OpenAPI_ServiceResponse>"));
        assertThrows(TourApiException.class, () -> client.parseItems("searchFestival2", """
                {"response":{"header":{"resultCode":"22","resultMsg":"LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"}}}"""));
        assertThrows(TourApiException.class, () -> client.parseItems("searchFestival2", null));
    }

    @Test
    void JSON으로_오는_게이트웨이_오류도_데이터_없음이_아니라_예외() {
        // 제공기관 서버 장애 때 실제로 이렇게 온다 (200 응답, 30초 뒤)
        assertThrows(TourApiException.class, () -> client.parseItems("searchFestival2", """
                {"OpenAPI_ServiceResponse":{"cmmMsgHeader":{"errMsg":"HTTP_ERROR","returnAuthMsg":"HTTP 에러","returnReasonCode":"04"}}}"""));
        assertThrows(TourApiException.class, () -> client.parseItems("searchFestival2", "{}"));
    }
}
