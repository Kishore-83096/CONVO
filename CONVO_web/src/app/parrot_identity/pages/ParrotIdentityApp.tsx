import { BrowserRouter, Navigate, Route, Routes } from "react-router"

import ConvoLayoutPage from "@/app/convo/layout/pages/ConvoLayoutPage"
import { WelcomePage } from "@/app/parrot_identity/auth"
import HealthPage from "@/app/parrot_identity/health/pages/HealthPage"

function ParrotIdentityApp() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<WelcomePage />} />
        <Route path="/userstart" element={<ConvoLayoutPage />} />
        <Route path="/health/all" element={<HealthPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default ParrotIdentityApp
