package com.triplanner.backend.service;

import com.triplanner.backend.domain.Trip;
import com.triplanner.backend.domain.TripChecklistItem;
import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.ChecklistItemRequest;
import com.triplanner.backend.dto.ChecklistItemResponse;
import com.triplanner.backend.repository.TripChecklistItemRepository;
import com.triplanner.backend.repository.TripRepository;
import com.triplanner.backend.repository.UserRepository;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

// 출발 전 준비 체크리스트: 여행을 처음 열 때 기간·지역·계절에 맞는 기본 항목을 만들고, 이후에는 사용자가 자유롭게 고친다
@Service
@Transactional
public class ChecklistService {

    static final String BOOKING = "BOOKING";
    static final String CHECK = "CHECK";
    static final String PACKING = "PACKING";
    static final String DEPARTURE = "DEPARTURE";
    static final String CUSTOM = "CUSTOM";

    private static final int MAX_ITEMS_PER_TRIP = 50;
    private static final String JEJU = "제주도";
    private static final ZoneId KST = ZoneId.of("Asia/Seoul");

    private final TripChecklistItemRepository checklistRepository;
    private final TripRepository tripRepository;
    private final UserRepository userRepository;

    public ChecklistService(
            TripChecklistItemRepository checklistRepository,
            TripRepository tripRepository,
            UserRepository userRepository
    ) {
        this.checklistRepository = checklistRepository;
        this.tripRepository = tripRepository;
        this.userRepository = userRepository;
    }

    public List<ChecklistItemResponse> getChecklist(String email, Long tripId) {
        Trip trip = getOwnedTrip(email, tripId);
        if (!trip.isChecklistInitialized()) {
            int order = 0;
            // 여행을 늦게 만든 사용자에게 만들자마자 '기한 지남'이 뜨지 않도록, 처음부터 기한이 지난 기본 항목은 만들지 않는다
            List<Draft> drafts = defaultItems(trip.getRegion(), trip.getStartDate(), trip.getEndDate());
            for (Draft draft : withoutAlreadyPastDue(drafts, trip.getStartDate(), LocalDate.now(KST))) {
                checklistRepository.save(new TripChecklistItem(trip, draft.content(), draft.category(), draft.dueOffsetDays(), order++));
            }
            trip.markChecklistInitialized();
        }
        return list(trip);
    }

    public ChecklistItemResponse addItem(String email, Long tripId, ChecklistItemRequest request) {
        Trip trip = getOwnedTrip(email, tripId);
        // 기본 항목이 아직 없는 여행에 먼저 직접 추가해도 기본 항목이 함께 만들어지도록 한다
        List<ChecklistItemResponse> current = getChecklist(email, tripId);
        if (current.size() >= MAX_ITEMS_PER_TRIP) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "체크리스트는 여행당 " + MAX_ITEMS_PER_TRIP + "개까지 만들 수 있어요.");
        }
        int nextOrder = checklistRepository.findByTrip_TripIdOrderByDueOffsetDaysDescSortOrderAscItemIdAsc(tripId).stream()
                .mapToInt(TripChecklistItem::getSortOrder).max().orElse(-1) + 1;
        TripChecklistItem saved = checklistRepository.save(
                new TripChecklistItem(trip, request.content().trim(), CUSTOM, request.dueOffsetDays(), nextOrder));
        return toResponse(trip, saved);
    }

    public ChecklistItemResponse setChecked(String email, Long tripId, Long itemId, boolean checked) {
        Trip trip = getOwnedTrip(email, tripId);
        TripChecklistItem item = getItemInTrip(trip, itemId);
        item.setChecked(checked);
        return toResponse(trip, item);
    }

    public void deleteItem(String email, Long tripId, Long itemId) {
        Trip trip = getOwnedTrip(email, tripId);
        checklistRepository.delete(getItemInTrip(trip, itemId));
    }

    private List<ChecklistItemResponse> list(Trip trip) {
        return checklistRepository.findByTrip_TripIdOrderByDueOffsetDaysDescSortOrderAscItemIdAsc(trip.getTripId()).stream()
                .map(item -> toResponse(trip, item))
                .toList();
    }

    private ChecklistItemResponse toResponse(Trip trip, TripChecklistItem item) {
        return new ChecklistItemResponse(
                item.getItemId(),
                item.getContent(),
                item.getCategory(),
                item.getDueOffsetDays(),
                trip.getStartDate().minusDays(item.getDueOffsetDays()),
                item.isChecked()
        );
    }

    private Trip getOwnedTrip(String email, Long tripId) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "사용자를 찾을 수 없습니다."));
        Trip trip = tripRepository.findById(tripId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "여행을 찾을 수 없습니다."));
        if (!trip.getUser().getUserId().equals(user.getUserId())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "본인의 여행만 이용할 수 있습니다.");
        }
        return trip;
    }

    private TripChecklistItem getItemInTrip(Trip trip, Long itemId) {
        TripChecklistItem item = checklistRepository.findById(itemId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "체크리스트 항목을 찾을 수 없습니다."));
        if (!item.getTrip().getTripId().equals(trip.getTripId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "체크리스트 항목을 찾을 수 없습니다.");
        }
        return item;
    }

    record Draft(String content, String category, int dueOffsetDays) {
    }

    // 기한(출발일 - dueOffsetDays)이 오늘보다 이미 지난 항목을 뺀다.
    // 예: 출발이 5일 뒤이면 D-7 항목(기한이 2일 전)을, 2일 뒤이면 D-7·D-3 항목을 만들지 않는다
    static List<Draft> withoutAlreadyPastDue(List<Draft> drafts, LocalDate startDate, LocalDate today) {
        return drafts.stream()
                .filter(draft -> !startDate.minusDays(draft.dueOffsetDays()).isBefore(today))
                .toList();
    }

    // 기간(박 수)·지역·출발 계절에 따라 달라지는 기본 항목. 기한은 출발일 기준 며칠 전인지로 둔다
    static List<Draft> defaultItems(String region, LocalDate startDate, LocalDate endDate) {
        long nights = ChronoUnit.DAYS.between(startDate, endDate);
        boolean jeju = JEJU.equals(region);
        int month = startDate.getMonthValue();
        List<Draft> items = new ArrayList<>();

        // D-7: 예약
        items.add(new Draft(jeju ? "항공권·렌터카 예약 확인" : "교통편 예약 확인 (KTX·버스·렌터카 등)", BOOKING, 7));
        if (nights >= 1) {
            items.add(new Draft("숙소 예약 확인 (체크인 시간·위치)", BOOKING, 7));
        }
        items.add(new Draft("방문할 곳의 예약·입장권 확인", BOOKING, 7));

        // D-3: 확인
        items.add(new Draft("날씨·기상특보·대기질 확인 (앱 알림 탭)", CHECK, 3));
        items.add(new Draft("방문할 곳의 운영시간·휴무일 확인", CHECK, 3));
        items.add(new Draft("일정의 동선·시간 최종 점검", CHECK, 3));

        // D-1: 짐
        items.add(new Draft("신분증·결제수단(카드·현금) 챙기기", PACKING, 1));
        items.add(new Draft("휴대폰 충전기·보조배터리 챙기기", PACKING, 1));
        items.add(new Draft("상비약·마스크 챙기기", PACKING, 1));
        if (nights >= 1) {
            items.add(new Draft("세면도구·갈아입을 옷 챙기기", PACKING, 1));
        }
        if (month == 6 || month == 7) {
            items.add(new Draft("우산·우비 챙기기 (장마철)", PACKING, 1));
        }
        if (month >= 6 && month <= 8) {
            items.add(new Draft("자외선 차단제·모자·시원한 옷 챙기기", PACKING, 1));
        } else if (month == 12 || month <= 2) {
            items.add(new Draft("방한 의류·핫팩 챙기기", PACKING, 1));
        } else {
            items.add(new Draft("일교차에 대비한 겉옷 챙기기", PACKING, 1));
        }
        if (jeju) {
            items.add(new Draft("항공편 결항·지연 정보 확인", CHECK, 1));
        }

        // D-0: 출발 당일
        items.add(new Draft("출발 시각·집합 장소 확인", DEPARTURE, 0));
        if (nights >= 1) {
            items.add(new Draft("가스·전기·문단속 확인", DEPARTURE, 0));
        }
        return items;
    }
}
