import { Link } from 'react-router-dom'
import { MapIcon } from '../components/Icons.jsx'

// 없는 주소로 들어왔을 때. 머리글은 그대로 두고 갈 곳을 알려 준다
export default function NotFound() {
  return (
    <div className="empty-state">
      <span className="empty-state__icon"><MapIcon size={24} /></span>
      <h1 className="empty-state__title">찾으시는 페이지가 없어요</h1>
      <p className="empty-state__desc">주소가 잘못되었거나 없어진 페이지예요. 홈에서 다시 시작해 주세요.</p>
      <Link to="/" className="btn btn-primary">홈으로 가기</Link>
    </div>
  )
}
