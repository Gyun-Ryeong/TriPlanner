import { useTripAlerts } from '../lib/tripAlertsContext.js'

// 푸터 저작권 문구의 '©' 글자가 곧 시연용 숨김 버튼이다. 누르면 종 알림에 가짜 알림이 들어오고, 다시 누르면 원래대로 돌아간다.
// 로그인한 상태에서만 동작한다 (종 알림이 보일 때만 의미가 있다)
export default function DemoAlertToggle() {
  const { demoOn, toggleDemo } = useTripAlerts()
  return (
    <button type="button" className="demo-alert-toggle" aria-pressed={demoOn} onClick={toggleDemo}>
      ©
    </button>
  )
}
