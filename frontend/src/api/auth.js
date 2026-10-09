import { apiRequest } from './client.js'

// consents: { terms, privacy } 는 필수 동의, { tripAlerts, thirdParty, marketing } 는 선택 동의
export function signup({ email, password, nickname, phone, consents }) {
  return apiRequest('/api/auth/signup', {
    method: 'POST',
    body: {
      email,
      password,
      nickname,
      phone,
      agreeTerms: consents.terms,
      agreePrivacy: consents.privacy,
      agreeTripAlerts: consents.tripAlerts,
      agreeThirdParty: consents.thirdParty,
      agreeMarketing: consents.marketing,
    },
  })
}

export function login({ email, password }) {
  return apiRequest('/api/auth/login', { method: 'POST', body: { email, password } })
}
