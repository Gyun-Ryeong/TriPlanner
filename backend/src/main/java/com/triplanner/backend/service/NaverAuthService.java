package com.triplanner.backend.service;

import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.NaverProfileResponse;
import com.triplanner.backend.dto.NaverTokenResponse;
import com.triplanner.backend.repository.UserRepository;
import com.triplanner.backend.security.JwtProvider;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.util.UriComponentsBuilder;

@Service
public class NaverAuthService {

    private final RestClient restClient = RestClient.create();

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtProvider jwtProvider;

    @Value("${naver.login.client-id}")
    private String clientId;

    @Value("${naver.login.client-secret}")
    private String clientSecret;

    @Value("${naver.login.redirect-uri}")
    private String redirectUri;

    @Value("${naver.login.frontend-redirect-base}")
    private String frontendRedirectBase;

    public NaverAuthService(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtProvider jwtProvider) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtProvider = jwtProvider;
    }

    public String buildAuthorizeUrl() {
        return UriComponentsBuilder.fromUriString("https://nid.naver.com/oauth2.0/authorize")
                .queryParam("response_type", "code")
                .queryParam("client_id", clientId)
                .queryParam("redirect_uri", redirectUri)
                .queryParam("state", jwtProvider.generateState())
                .build()
                .toUriString();
    }

    public String handleCallback(String code, String state, String naverError) {
        if (naverError != null) {
            return errorRedirect("네이버 로그인이 취소되었습니다.");
        }
        if (state == null || !jwtProvider.isValidState(state)) {
            return errorRedirect("네이버 로그인 요청이 유효하지 않습니다. 다시 시도해주세요.");
        }
        if (code == null) {
            return errorRedirect("네이버 인증 코드를 받지 못했습니다.");
        }

        NaverTokenResponse tokenResponse;
        try {
            tokenResponse = restClient.get()
                    .uri(uriBuilder -> uriBuilder
                            .scheme("https").host("nid.naver.com").path("/oauth2.0/token")
                            .queryParam("grant_type", "authorization_code")
                            .queryParam("client_id", clientId)
                            .queryParam("client_secret", clientSecret)
                            .queryParam("code", code)
                            .queryParam("state", state)
                            .build())
                    .retrieve()
                    .body(NaverTokenResponse.class);
        } catch (RestClientException e) {
            return errorRedirect("네이버 인증 서버와 통신 중 오류가 발생했습니다.");
        }

        if (tokenResponse == null || tokenResponse.accessToken() == null) {
            return errorRedirect("네이버 액세스 토큰을 발급받지 못했습니다.");
        }

        NaverProfileResponse profileResponse;
        try {
            profileResponse = restClient.get()
                    .uri("https://openapi.naver.com/v1/nid/me")
                    .header("Authorization", "Bearer " + tokenResponse.accessToken())
                    .retrieve()
                    .body(NaverProfileResponse.class);
        } catch (RestClientException e) {
            return errorRedirect("네이버 프로필 조회 중 오류가 발생했습니다.");
        }

        if (profileResponse == null || profileResponse.response() == null || profileResponse.response().email() == null) {
            return errorRedirect("네이버 계정에서 이메일 정보를 가져오지 못했습니다. 이메일 제공에 동의해주세요.");
        }

        String email = profileResponse.response().email();
        String nickname = profileResponse.response().nickname() != null ? profileResponse.response().nickname() : email;

        User user = userRepository.findByEmail(email)
                .orElseGet(() -> userRepository.save(new User(email, passwordEncoder.encode(UUID.randomUUID().toString()), nickname)));

        String jwt = jwtProvider.generateToken(user.getUserId(), user.getEmail());

        return UriComponentsBuilder.fromUriString(frontendRedirectBase + "/oauth/naver/callback")
                .queryParam("token", jwt)
                .queryParam("userId", user.getUserId())
                .queryParam("email", user.getEmail())
                .queryParam("nickname", user.getNickname())
                .build()
                .encode()
                .toUriString();
    }

    private String errorRedirect(String message) {
        return UriComponentsBuilder.fromUriString(frontendRedirectBase + "/login")
                .queryParam("error", message)
                .build()
                .encode()
                .toUriString();
    }
}
