import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { saveAuth } from '../api/authStorage.js'

export default function NaverCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  useEffect(() => {
    const token = searchParams.get('token')
    const userId = searchParams.get('userId')
    const email = searchParams.get('email')
    const nickname = searchParams.get('nickname')

    if (!token) {
      navigate('/login?error=네이버 로그인에 실패했습니다.')
      return
    }

    saveAuth({ token, userId: Number(userId), email, nickname })
    navigate('/')
  }, [searchParams, navigate])

  return null
}
