import { Navigate, Outlet } from "react-router-dom";

import { userHomePath } from "./auth-routes";
import { useAuth } from "./use-auth";

export function RedirectIfAuthenticated() {
  const { isAuthenticated, session } = useAuth();

  if (isAuthenticated) {
    return <Navigate to={userHomePath(session)} replace />;
  }

  return <Outlet />;
}
