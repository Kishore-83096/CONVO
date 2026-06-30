import {
  Navigate,
  Outlet,
  useParams,
} from "react-router-dom";

import { userHomePath } from "./auth-routes";
import { useAuth } from "./use-auth";

export function RequireUsername() {
  const { session } = useAuth();
  const { username } = useParams();

  if (!session) {
    return <Navigate to="/login" replace />;
  }

  if (username !== session.user.username) {
    return <Navigate to={userHomePath(session)} replace />;
  }

  return <Outlet />;
}
