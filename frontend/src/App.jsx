import { Routes, Route } from 'react-router-dom'
import MainLayout from './components/MainLayout.jsx'
import Login from './pages/Login.jsx'
import Signup from './pages/Signup.jsx'
import Home from './pages/Home.jsx'
import Chatbot from './pages/Chatbot.jsx'
import TripSchedule from './pages/TripSchedule.jsx'
import NewTrip from './pages/NewTrip.jsx'
import MyTrips from './pages/MyTrips.jsx'
import TripStats from './pages/TripStats.jsx'
import ProfileEdit from './pages/ProfileEdit.jsx'
import Alerts from './pages/Alerts.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />

      <Route element={<MainLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/schedule" element={<TripSchedule />} />
        <Route path="/chatbot" element={<Chatbot />} />
        <Route path="/mytrips" element={<MyTrips />} />
        <Route path="/mytrips/stats" element={<TripStats />} />
        <Route path="/mytrips/edit" element={<ProfileEdit />} />
        <Route path="/trips/new" element={<NewTrip />} />
        <Route path="/alerts" element={<Alerts />} />
      </Route>
    </Routes>
  )
}
