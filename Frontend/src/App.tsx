import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import { RequireAuth } from "./components/RequireAuth";
import { Splash } from "./components/Splash";
import About from "./pages/About";
import Contact from "./pages/Contact";
import Dashboard from "./pages/Dashboard";
import Faq from "./pages/Faq";
import Home from "./pages/Home";
import Live from "./pages/Live";
import Login from "./pages/Login";
import Responder from "./pages/Responder";
import Volunteers from "./pages/Volunteers";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public. The deployment URL gets handed to testers and shared
            around, and someone who needs help should not land in an
            operations console. */}
        <Route
          path="/"
          element={
            <Splash>
              <Home />
            </Splash>
          }
        />
        <Route path="/about" element={<About />} />
        <Route path="/faq" element={<Faq />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/login" element={<Login />} />

        {/* The handoff link is public by design: it goes to a fire or
            ambulance desk that will never have a SafeZone account, and the
            token in the URL is the credential. */}
        <Route path="/r/:token" element={<Responder />} />

        {/* Behind the login. These show reporter names, numbers and exact
            locations, and who is on duty and where.

            The splash wraps the landing page and the control room, and not
            the router. A handoff link is deliberately left out: that one is
            opened by a rescue crew reading a case in the rain, and branding
            must never stand between them and an address. It shows once per
            page load, so moving between pages does not replay it. */}
        <Route
          path="/control"
          element={
            <RequireAuth>
              <Splash>
                <Dashboard />
              </Splash>
            </RequireAuth>
          }
        />
        <Route
          path="/live"
          element={
            <RequireAuth>
              <Live />
            </RequireAuth>
          }
        />
        <Route
          path="/volunteers"
          element={
            <RequireAuth>
              <Volunteers />
            </RequireAuth>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
