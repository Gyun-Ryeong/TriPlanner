package com.triplanner.backend.service;

import com.triplanner.backend.domain.Place;
import com.triplanner.backend.domain.Trip;
import com.triplanner.backend.domain.TripItem;
import com.triplanner.backend.repository.TripItemRepository;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

// 챗봇이 회원 취향을 알 수 있게, 회원이 '내 여행'에 저장한 장소를 짧게 요약한다 (DB 구조는 바꾸지 않는다)
// 요약: 장소 유형별 수, 장소 이름 (최근 것부터), 다녀온 장소 content_id, 다녀온 지역
@Service
public class ChatProfileService {

    private static final int MAX_ITEMS = 200;
    private static final int MAX_NAMES = 60;

    private final TripItemRepository tripItemRepository;

    public ChatProfileService(TripItemRepository tripItemRepository) {
        this.tripItemRepository = tripItemRepository;
    }

    @Transactional(readOnly = true)
    public Map<String, Object> profileOf(String email) {
        List<TripItem> items = tripItemRepository.findRecentWithPlaceByEmail(email, PageRequest.of(0, MAX_ITEMS));
        Map<String, Integer> categories = new LinkedHashMap<>();
        Set<String> names = new LinkedHashSet<>();
        Set<String> visited = new LinkedHashSet<>();
        Set<String> regions = new LinkedHashSet<>();
        for (TripItem item : items) {
            Place place = item.getPlace();
            if (place == null) {
                continue;
            }
            if (place.getCategory() != null && !place.getCategory().isBlank()) {
                categories.merge(place.getCategory(), 1, Integer::sum);
            }
            if (names.size() < MAX_NAMES && place.getName() != null) {
                names.add(place.getName());
            }
            if (place.getContentId() != null && !place.getContentId().isBlank()) {
                visited.add(place.getContentId());
            }
            Trip trip = item.getTripDay().getTrip();
            String region = String.join(" ", nonBlank(trip.getRegion(), trip.getCity()));
            if (!region.isBlank()) {
                regions.add(region);
            }
        }
        Map<String, Object> profile = new LinkedHashMap<>();
        profile.put("categories", categories);
        profile.put("place_names", new ArrayList<>(names));
        profile.put("visited_ids", new ArrayList<>(visited));
        profile.put("regions", new ArrayList<>(regions));
        return profile;
    }

    private static List<String> nonBlank(String... values) {
        List<String> out = new ArrayList<>();
        for (String v : values) {
            if (v != null && !v.isBlank()) {
                out.add(v.trim());
            }
        }
        return out;
    }
}
