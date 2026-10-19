package com.triplanner.backend.service;

import com.triplanner.backend.domain.Trip;
import com.triplanner.backend.domain.TripDay;
import com.triplanner.backend.domain.User;
import com.triplanner.backend.dto.ChecklistItemResponse;
import com.triplanner.backend.dto.PrepAlertsResponse;
import com.triplanner.backend.dto.PrepAlertsResponse.PrepAlert;
import com.triplanner.backend.dto.PrepAlertsResponse.TripPrepAlerts;
import com.triplanner.backend.repository.TripDayRepository;
import com.triplanner.backend.repository.TripItemRepository;
import com.triplanner.backend.repository.TripRepository;
import com.triplanner.backend.repository.UserRepository;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

// 일정 변경·준비 알림: 아직 출발하지 않은 여행의 준비 상태(오늘까지인 체크리스트 항목, 비어 있는 일정)를 요청 때마다 계산한다
@Service
@Transactional
public class PrepAlertService {

    static final String DANGER = "DANGER";
    static final String CAUTION = "CAUTION";

    private static final ZoneId KST = ZoneId.of("Asia/Seoul");
    // 출발이 이 일수 안으로 들어오면 비어 있는 일정을 알려준다
    private static final int EMPTY_DAY_WINDOW_DAYS = 7;

    private final UserRepository userRepository;
    private final TripRepository tripRepository;
    private final TripDayRepository tripDayRepository;
    private final TripItemRepository tripItemRepository;
    private final ChecklistService checklistService;

    public PrepAlertService(
            UserRepository userRepository,
            TripRepository tripRepository,
            TripDayRepository tripDayRepository,
            TripItemRepository tripItemRepository,
            ChecklistService checklistService
    ) {
        this.userRepository = userRepository;
        this.tripRepository = tripRepository;
        this.tripDayRepository = tripDayRepository;
        this.tripItemRepository = tripItemRepository;
        this.checklistService = checklistService;
    }

    public PrepAlertsResponse getAlerts(String email) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "사용자를 찾을 수 없습니다."));
        if (!user.isNotifyScheduleAlerts()) {
            return new PrepAlertsResponse(false, List.of());
        }

        LocalDate today = LocalDate.now(KST);
        List<TripPrepAlerts> result = new ArrayList<>();
        // 이미 출발했거나 끝난 여행은 준비할 일이 없으므로 제외한다
        for (Trip trip : tripRepository.findByUser_UserIdOrderByStartDateAsc(user.getUserId())) {
            if (trip.getStartDate() == null || trip.getStartDate().isBefore(today)) {
                continue;
            }
            long daysUntilStart = ChronoUnit.DAYS.between(today, trip.getStartDate());
            List<PrepAlert> alerts = new ArrayList<>();

            checklistAlert(email, trip, today).ifPresent(alerts::add);
            if (daysUntilStart <= EMPTY_DAY_WINDOW_DAYS) {
                emptyDayAlert(trip).ifPresent(alerts::add);
            }

            if (!alerts.isEmpty()) {
                result.add(new TripPrepAlerts(
                        trip.getTripId(), trip.getTitle(), trip.getRegion(), trip.getStartDate(), daysUntilStart, alerts));
            }
        }
        return new PrepAlertsResponse(true, result);
    }

    // 체크하지 않은 항목 중 기한이 오늘인 것. 기한이 지난 항목은 알림에서 뺀다 (체크리스트 화면에서만 '기한 지남'으로 표시)
    private Optional<PrepAlert> checklistAlert(String email, Trip trip, LocalDate today) {
        List<ChecklistItemResponse> items = checklistService.getChecklist(email, trip.getTripId());
        long dueToday = items.stream().filter(i -> !i.checked() && i.dueDate().isEqual(today)).count();
        if (dueToday > 0) {
            return Optional.of(new PrepAlert(CAUTION, "CHECKLIST", "체크리스트에 오늘까지인 항목이 " + dueToday + "개 있어요."));
        }
        return Optional.empty();
    }

    // 장소·메모가 하나도 없는 날
    private Optional<PrepAlert> emptyDayAlert(Trip trip) {
        List<TripDay> days = tripDayRepository.findByTrip_TripIdOrderByDayNumberAsc(trip.getTripId());
        List<Integer> emptyDays = days.stream()
                .filter(day -> tripItemRepository.findByTripDay_TripDayIdOrderByVisitOrderAsc(day.getTripDayId()).isEmpty())
                .map(TripDay::getDayNumber)
                .toList();
        if (emptyDays.isEmpty()) {
            return Optional.empty();
        }
        String label = emptyDays.stream().map(String::valueOf).collect(Collectors.joining("·"));
        return Optional.of(new PrepAlert(CAUTION, "EMPTY_DAY", label + "일차 일정이 비어 있어요."));
    }
}
