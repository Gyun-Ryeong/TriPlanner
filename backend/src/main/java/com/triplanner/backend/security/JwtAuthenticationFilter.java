package com.triplanner.backend.security;

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

    public JwtAuthenticationFilter(JwtProvider jwtProvider, AdminAccounts adminAccounts) {
        this.jwtProvider = jwtProvider;
        this.adminAccounts = adminAccounts;
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

            if (jwtProvider.isValid(token)) {
                String email = jwtProvider.getEmail(token);
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
