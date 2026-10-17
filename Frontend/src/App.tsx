import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import ControlRoom from './pages/ControlRoom'
import Home from './pages/Home'
import Responder from './pages/Responder'
import Volunteers from './pages/Volunteers'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/control" element={<ControlRoom />} />
        <Route path="/r/:token" element={<Responder />} />
        <Route path="/volunteers" element={<Volunteers />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
