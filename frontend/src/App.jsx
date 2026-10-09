import { Routes, Route } from 'react-router-dom'
import MainLayout from './components/MainLayout.jsx'
import RequireAuth from './components/RequireAuth.jsx'
import RequireAdmin from './components/RequireAdmin.jsx'
import Login from './pages/Login.jsx'
import Signup from './pages/Signup.jsx'
import NaverCallback from './pages/NaverCallback.jsx'
import Home from './pages/Home.jsx'
import Chatbot from './pages/Chatbot.jsx'
import TripSchedule from './pages/TripSchedule.jsx'
import NewTrip from './pages/NewTrip.jsx'
import MyTrips from './pages/MyTrips.jsx'
import TripStats from './pages/TripStats.jsx'
import ProfileEdit from './pages/ProfileEdit.jsx'
import Alerts from './pages/Alerts.jsx'
import Admin from './pages/Admin.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/oauth/naver/callback" element={<NaverCallback />} />

      <Route element={<MainLayout />}>
        <Route path="/" element={<Home />} />

        <Route element={<RequireAuth />}>
          <Route path="/schedule" element={<TripSchedule />} />
          <Route path="/schedule/:tripId" element={<TripSchedule />} />
          <Route path="/chatbot" element={<Chatbot />} />
          <Route path="/mytrips" element={<MyTrips />} />
          <Route path="/mytrips/stats" element={<TripStats />} />
          <Route path="/mytrips/edit" element={<ProfileEdit />} />
          <Route path="/trips/new" element={<NewTrip />} />
          <Route path="/trips/:tripId/plan" element={<TripSchedule mode="plan" />} />
          <Route path="/alerts" element={<Alerts />} />
        </Route>

        <Route element={<RequireAdmin />}>
          <Route path="/admin" element={<Admin />} />
        </Route>
      </Route>
    </Routes>
  )
}
