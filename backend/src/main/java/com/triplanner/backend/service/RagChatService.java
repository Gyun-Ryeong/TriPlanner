package com.triplanner.backend.service;

import tools.jackson.databind.JsonNode;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

// rag_project 의 FastAPI 서버(api_server.py)로 대화를 전달한다
@Service
public class RagChatService {

    private final RestClient restClient;

    public RagChatService(
            @Value("${rag.base-url}") String baseUrl,
            @Value("${rag.read-timeout-seconds}") long readTimeoutSeconds
    ) {
        // 일정 생성은 로컬 LLM 을 거쳐 수 분이 걸릴 수 있어 읽기 시간 제한을 넉넉히 둔다
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Duration.ofSeconds(5));
        requestFactory.setReadTimeout(Duration.ofSeconds(readTimeoutSeconds));

        this.restClient = RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(requestFactory)
                .build();
    }

    public JsonNode chat(String sessionId, String message, boolean debug) {
        Map<String, Object> body = new HashMap<>();
        body.put("session_id", sessionId);
        body.put("message", message == null ? "" : message);
        body.put("debug", debug);

        try {
            return restClient.post()
                    .uri("/chat")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(JsonNode.class);
        } catch (ResourceAccessException e) {
            // 연결 실패와 응답 시간 초과 모두 여기로 온다
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "챗봇 서버에 연결할 수 없거나 응답이 너무 오래 걸립니다. 잠시 후 다시 시도해 주세요.");
        } catch (RestClientException e) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "챗봇이 응답하지 못했습니다. 잠시 후 다시 시도해 주세요.");
        }
    }

    // 관리자 페이지의 챗봇 서버 상태 표시용
    public boolean isServerUp() {
        try {
            JsonNode health = restClient.get().uri("/health").retrieve().body(JsonNode.class);
            return health != null && "ok".equals(health.path("status").asText());
        } catch (RestClientException e) {
            return false;
        }
    }

    public void reset(String sessionId) {
        try {
            restClient.delete()
                    .uri("/chat/{sessionId}", sessionId)
                    .retrieve()
                    .toBodilessEntity();
        } catch (RestClientException e) {
            // 세션은 RAG 서버에서 2시간 뒤 자동으로 사라지므로 초기화 실패는 무시해도 된다
        }
    }
}
