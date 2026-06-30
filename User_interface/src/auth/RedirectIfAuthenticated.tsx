import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./use-auth";

export function RedirectIfAuthenticated() {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate to="/app" replace />;
  }

  return <Outlet />;
}