import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { UserIcon } from './Icons.jsx'
import './UserMenu.css'

// 머리글의 사용자 아이콘. 누르면 마이페이지 / 로그아웃을 고르는 작은 메뉴가 열린다
export default function UserMenu({ onLogout }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)
  const buttonRef = useRef(null)

  // 바깥을 누르거나 Esc 를 누르면 닫힌다
  useEffect(() => {
    if (!open) return undefined
    const onPointer = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false)
    }
    const onKey = (event) => {
      if (event.key === 'Escape') {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="user-menu" ref={rootRef}>
      <button
        ref={buttonRef}
        type="button"
        className="user-menu__button"
        aria-label="내 메뉴"
        title="내 메뉴"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        <UserIcon size={18} />
      </button>
      {open && (
        <div className="user-menu__panel">
          <Link to="/mytrips" className="user-menu__item" onClick={() => setOpen(false)}>
            마이페이지
          </Link>
          <button type="button" className="user-menu__item" onClick={onLogout}>
            로그아웃
          </button>
        </div>
      )}
    </div>
  )
}
