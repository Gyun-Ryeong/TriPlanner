import { useNavigate } from 'react-router-dom'
import { ArrowLeftIcon } from './Icons.jsx'

// 이전 화면으로 돌아가는 버튼. 주소창으로 바로 들어와 돌아갈 기록이 없으면 fallback 주소로 보낸다
export default function BackButton({ fallback = '/' }) {
  const navigate = useNavigate()

  function handleClick() {
    if (window.history.state?.idx > 0) navigate(-1)
    else navigate(fallback)
  }

  return (
    <button type="button" className="btn btn-sm" onClick={handleClick}>
      <ArrowLeftIcon size={15} /> 뒤로가기
    </button>
  )
}
