import { BrowserRouter, Navigate, Route, Routes } from "react-router"

import ConvoLayoutPage from "@/app/convo/layout/pages/ConvoLayoutPage"
import { WelcomePage } from "@/app/convo_identity/auth"
import { userHomePath } from "@/app/convo_identity/auth/auth-routes"
import { getAuthSession } from "@/app/convo_identity/auth/auth-session"
import HealthPage from "@/app/convo_identity/health/pages/HealthPage"

function UserStartRedirect() {
  return <Navigate to={userHomePath(getAuthSession())} replace />
}

function ConvoIdentityApp() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<WelcomePage />} />
        <Route path="/health/all" element={<HealthPage />} />
        <Route path="/userstart" element={<UserStartRedirect />} />
        <Route path="/:username" element={<ConvoLayoutPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default ConvoIdentityApp
