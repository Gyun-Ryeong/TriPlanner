package com.triplanner.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.ConnectException;
import java.net.SocketTimeoutException;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.ResourceAccessException;

class ChatbotErrorLogServiceTest {

    @Test
    void readTimeoutIsClassifiedAsTimeout() {
        ResourceAccessException error = new ResourceAccessException("I/O error", new SocketTimeoutException("Read timed out"));

        assertTrue(RagChatService.isTimeout(error));
    }

    @Test
    void connectFailuresAreNotTimeouts() {
        assertFalse(RagChatService.isTimeout(new ResourceAccessException("I/O error", new ConnectException("Connection refused"))));
        assertFalse(RagChatService.isTimeout(new ResourceAccessException("I/O error", new SocketTimeoutException("Connect timed out"))));
    }

    @Test
    void ragStatusCodesMapToCategories() {
        assertEquals(ChatbotErrorLogService.AI_MODEL, RagChatService.categoryOfStatus(503));
        assertEquals(ChatbotErrorLogService.SERVER_ERROR, RagChatService.categoryOfStatus(500));
        assertEquals(ChatbotErrorLogService.SERVER_ERROR, RagChatService.categoryOfStatus(502));
        assertEquals(ChatbotErrorLogService.BAD_REQUEST, RagChatService.categoryOfStatus(400));
        assertEquals(ChatbotErrorLogService.BAD_REQUEST, RagChatService.categoryOfStatus(422));
        assertEquals(ChatbotErrorLogService.OTHER, RagChatService.categoryOfStatus(302));
    }

    @Test
    void truncateKeepsOnlyTheFrontAndTreatsBlankAsNull() {
        assertNull(ChatbotErrorLogService.truncate(null, 100));
        assertNull(ChatbotErrorLogService.truncate("   ", 100));
        assertEquals("abc", ChatbotErrorLogService.truncate("  abc ", 100));
        assertEquals(100, ChatbotErrorLogService.truncate("가".repeat(300), ChatbotErrorLogService.QUERY_MAX_LENGTH).length());
    }
}
