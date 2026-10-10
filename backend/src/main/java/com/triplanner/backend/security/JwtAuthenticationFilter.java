package com.triplanner.backend.security;

import com.triplanner.backend.repository.UserRepository;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtProvider jwtProvider;
    private final AdminAccounts adminAccounts;
    private final UserRepository userRepository;

    public JwtAuthenticationFilter(JwtProvider jwtProvider, AdminAccounts adminAccounts, UserRepository userRepository) {
        this.jwtProvider = jwtProvider;
        this.adminAccounts = adminAccounts;
        this.userRepository = userRepository;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {
        String header = request.getHeader("Authorization");

        if (header != null && header.startsWith("Bearer ")) {
            String token = header.substring(7);

            // 탈퇴했거나 파기된 회원의 토큰은 만료 전이라도 인증하지 않는다
            String email = jwtProvider.isValid(token) ? jwtProvider.getEmail(token) : null;
            if (email != null && userRepository.existsByEmailAndWithdrawnAtIsNull(email)) {
                List<SimpleGrantedAuthority> authorities = adminAccounts.isAdmin(email)
                        ? List.of(new SimpleGrantedAuthority("ROLE_USER"), new SimpleGrantedAuthority(AdminAccounts.ROLE_ADMIN))
                        : List.of(new SimpleGrantedAuthority("ROLE_USER"));
                var authentication = new UsernamePasswordAuthenticationToken(email, null, authorities);
                SecurityContextHolder.getContext().setAuthentication(authentication);
            }
        }

        filterChain.doFilter(request, response);
    }
}
