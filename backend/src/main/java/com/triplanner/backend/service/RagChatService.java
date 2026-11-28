package com.triplanner.backend.service;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.JsonNodeFactory;
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
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;

// rag_project 의 FastAPI 서버(api_server.py)로 대화를 전달한다
@Service
public class RagChatService {

    private final RestClient restClient;
    private final ChatProfileService profileService;

    public RagChatService(
            @Value("${rag.base-url}") String baseUrl,
            @Value("${rag.read-timeout-seconds}") long readTimeoutSeconds,
            ChatProfileService profileService
    ) {
        this.profileService = profileService;
        // 일정 생성은 로컬 LLM 을 거쳐 수 분이 걸릴 수 있어 읽기 시간 제한을 넉넉히 둔다
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Duration.ofSeconds(5));
        requestFactory.setReadTimeout(Duration.ofSeconds(readTimeoutSeconds));

        this.restClient = RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(requestFactory)
                .build();
    }

    // email: 요청한 회원 (저장한 여행으로 만든 취향 요약을 함께 보낸다)
    public JsonNode chat(String email, String sessionId, String message) {
        Map<String, Object> body = new HashMap<>();
        body.put("session_id", sessionId);
        body.put("message", message == null ? "" : message);
        body.put("profile", profileOrEmpty(email));

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
        } catch (RestClientResponseException e) {
            // RAG 서버가 오류 상태로 응답한 경우
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "챗봇이 응답하지 못했습니다. 잠시 후 다시 시도해 주세요.");
        } catch (RestClientException e) {
            // 응답을 읽는 도중의 시간 초과 등 그 밖의 실패
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "챗봇이 응답하지 못했습니다. 잠시 후 다시 시도해 주세요.");
        }
    }

    // 회원이 저장한 여행으로 만든 취향 요약. 요약에 실패해도 대화는 그대로 진행한다
    private Map<String, Object> profileOrEmpty(String email) {
        try {
            return email == null ? Map.of() : profileService.profileOf(email);
        } catch (RuntimeException e) {
            return Map.of();
        }
    }

    // 사용자가 방금 보낸 말을 취소한다: RAG 서버가 그 말로 바꿔 둔 대화 기억을 되돌린다. 실패해도 화면은 이미 취소돼 있어 무시한다
    public void cancel(String sessionId) {
        try {
            restClient.post()
                    .uri("/chat/{sessionId}/cancel", sessionId)
                    .retrieve()
                    .toBodilessEntity();
        } catch (RestClientException e) {
            // RAG 서버에 닿지 않으면 되돌릴 대화 기억도 없다
        }
    }

    // 답을 기다리는 동안 RAG 서버가 지금 하는 일 ("날씨를 모으고 있어요" 등). 서버에 닿지 않으면 처리 중이 아닌 것으로 답한다
    public JsonNode progress(String sessionId) {
        try {
            JsonNode body = restClient.get()
                    .uri("/chat/{sessionId}/progress", sessionId)
                    .retrieve()
                    .body(JsonNode.class);
            if (body != null) {
                return body;
            }
        } catch (RestClientException e) {
            // 진행 상황은 보여주기용이라 실패해도 오류로 다루지 않는다
        }
        return JsonNodeFactory.instance.objectNode().put("busy", false).put("step", "").put("elapsed", 0);
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
