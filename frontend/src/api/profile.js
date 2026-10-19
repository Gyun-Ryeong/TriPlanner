import { apiRequest } from './client.js'
import { getAuth } from './authStorage.js'

function authToken() {
  return getAuth()?.token
}

export function getProfile() {
  return apiRequest('/api/me', { token: authToken() })
}

export function updateProfile({ nickname, phone }) {
  return apiRequest('/api/me', {
    method: 'PUT',
    body: { nickname, phone },
    token: authToken(),
  })
}

// 바꾸려는 설정만 넘긴다 (넘기지 않은 설정은 그대로 둔다)
export function updateNotifications({ tripAlertsEnabled, scheduleAlertsEnabled }) {
  return apiRequest('/api/me/notifications', {
    method: 'PUT',
    body: { tripAlertsEnabled, scheduleAlertsEnabled },
    token: authToken(),
  })
}

export function updateMarketingConsent({ marketingConsent }) {
  return apiRequest('/api/me/marketing', {
    method: 'PUT',
    body: { marketingConsent },
    token: authToken(),
  })
}

export function changePassword({ currentPassword, newPassword }) {
  return apiRequest('/api/me/password', {
    method: 'PUT',
    body: { currentPassword, newPassword },
    token: authToken(),
  })
}

// 탈퇴는 현재 비밀번호와 확인 문구('회원탈퇴')를 서버에서도 검사한다
export function withdraw({ password, confirmText }) {
  return apiRequest('/api/me/withdrawal', {
    method: 'POST',
    body: { password, confirmText },
    token: authToken(),
  })
}
