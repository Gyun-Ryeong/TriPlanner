package com.triplanner.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.WithdrawalRequest;
import com.triplanner.backend.repository.ChatbotErrorLogRepository;
import com.triplanner.backend.repository.RagQueryLogRepository;
import com.triplanner.backend.repository.TripChecklistItemRepository;
import com.triplanner.backend.repository.TripDayRepository;
import com.triplanner.backend.repository.TripItemRepository;
import com.triplanner.backend.repository.TripRepository;
import com.triplanner.backend.repository.UserRepository;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.server.ResponseStatusException;

class WithdrawalServiceTest {

    private static final String EMAIL = "member@test.local";

    private UserRepository userRepository;
    private PasswordEncoder passwordEncoder;
    private WithdrawalService service;
    private User user;

    @BeforeEach
    void setUp() {
        userRepository = mock(UserRepository.class);
        passwordEncoder = mock(PasswordEncoder.class);
        service = new WithdrawalService(
                userRepository,
                mock(TripRepository.class),
                mock(TripDayRepository.class),
                mock(TripItemRepository.class),
                mock(RagQueryLogRepository.class),
                mock(TripChecklistItemRepository.class),
                mock(ChatbotErrorLogRepository.class),
                passwordEncoder);

        user = new User(EMAIL, "encoded-password", "회원");
        when(userRepository.findByEmail(EMAIL)).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("right-password", "encoded-password")).thenReturn(true);
    }

    @Test
    void withdrawsWhenPasswordAndConfirmTextAreCorrect() {
        service.withdraw(EMAIL, new WithdrawalRequest("right-password", "회원탈퇴"));

        assertTrue(user.isWithdrawn());
    }

    @Test
    void wrongPasswordDoesNotWithdraw() {
        ResponseStatusException failure = assertThrows(ResponseStatusException.class,
                () -> service.withdraw(EMAIL, new WithdrawalRequest("wrong-password", "회원탈퇴")));

        assertEquals(HttpStatus.BAD_REQUEST, failure.getStatusCode());
        assertFalse(user.isWithdrawn());
    }

    @Test
    void wrongConfirmTextDoesNotWithdraw() {
        ResponseStatusException failure = assertThrows(ResponseStatusException.class,
                () -> service.withdraw(EMAIL, new WithdrawalRequest("right-password", "탈퇴")));

        assertEquals(HttpStatus.BAD_REQUEST, failure.getStatusCode());
        assertFalse(user.isWithdrawn());
    }
}
