import { Navigate, Route, Routes } from "react-router-dom";

import { LoginPage } from "../../features/auth/pages/LoginPage";
import { RegisterPage } from "../../features/auth/pages/RegisterPage";
import { IdentityHealthPage } from "../../features/health/pages/IdentityHealthPage";
import { MessengerHealthPage } from "../../features/health/pages/MessengerHealthPage";
import { AppShellPage } from "../../features/messages/pages/AppShellPage";
import { SettingsPage } from "../../features/settings/pages/SettingsPage";
import { WelcomePage } from "../../shared/ui/WelcomePage";
import { RequireAuth } from "./RequireAuth";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<WelcomePage />} />
      <Route path="/health/identity" element={<IdentityHealthPage />} />
      <Route path="/health/messenger" element={<MessengerHealthPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/app"
        element={
          <RequireAuth>
            <AppShellPage />
          </RequireAuth>
        }
      />

      <Route
        path="/settings"
        element={
          <RequireAuth>
            <SettingsPage />
          </RequireAuth>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}