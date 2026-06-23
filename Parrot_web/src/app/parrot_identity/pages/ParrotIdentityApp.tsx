import { HashRouter, Navigate, Route, Routes } from "react-router"

import { WelcomePage } from "@/app/parrot_identity/auth"
import HealthPage from "@/app/parrot_identity/health/pages/HealthPage"
import SharedLayoutPage from "@/app/shared/pages/SharedLayoutPage"

function ParrotIdentityApp() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<WelcomePage />} />
        <Route path="/userstart" element={<SharedLayoutPage />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  )
}

export default ParrotIdentityApp