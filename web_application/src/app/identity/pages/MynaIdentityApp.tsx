import { lazy, Suspense } from "react"
import { BrowserRouter, Navigate, Route, Routes } from "react-router"

import { userHomePath } from "@/app/identity/auth/auth-routes"
import { getAuthSession } from "@/app/identity/auth/auth-session"
import { NotFoundPage, PublicPage } from "@/app/public/PublicPages"
import SeoMeta from "@/app/seo/SeoMeta"

const WorkspaceLayoutPage = lazy(() => import("@/app/workspace/layout/pages/WorkspaceLayoutPage"))
const HealthPage = lazy(() => import("@/app/identity/health/pages/HealthPage"))
const WelcomePage = lazy(() => import("@/app/identity/auth/pages/WelcomePage"))

function UserStartRedirect() {
  return (
    <>
      <SeoMeta
        canonicalPath="/userstart"
        description="Myna private application redirect."
        robots="noindex, nofollow"
        title="Myna App Redirect"
      />
      <Navigate to={userHomePath(getAuthSession())} replace />
    </>
  )
}

function MynaIdentityApp() {
  return (
    <BrowserRouter>
      <Suspense fallback={null}>
        <Routes>
          <Route path="/" element={<PublicPage pageKey="home" />} />
          <Route path="/features" element={<PublicPage pageKey="features" />} />
          <Route path="/security" element={<PublicPage pageKey="security" />} />
          <Route path="/privacy" element={<PublicPage pageKey="privacy" />} />
          <Route path="/about" element={<PublicPage pageKey="about" />} />
          <Route path="/contact" element={<PublicPage pageKey="contact" />} />
          <Route path="/login" element={<WelcomePage initialTab="login" />} />
          <Route path="/register" element={<WelcomePage initialTab="register" />} />
          <Route path="/health/all" element={<HealthPage />} />
          <Route path="/userstart" element={<UserStartRedirect />} />
          <Route path="/:username" element={<WorkspaceLayoutPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default MynaIdentityApp
