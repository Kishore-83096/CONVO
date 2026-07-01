import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../../app/providers/useAuth";
import { Button } from "../../../shared/ui/Button";
import { useLogoutUser } from "../hooks";

type LogoutButtonProps = {
  fullWidth?: boolean;
};

export function LogoutButton({ fullWidth = false }: LogoutButtonProps) {
  const [logoutError, setLogoutError] = useState("");

  const navigate = useNavigate();
  const { clearSession } = useAuth();
  const logoutMutation = useLogoutUser();

  async function handleLogout() {
    setLogoutError("");

    const result = await logoutMutation.mutateAsync();

    if (!result.ok) {
      setLogoutError(
        "Server logout failed, but your local session was cleared safely.",
      );
    }

    await clearSession();

    navigate("/login", {
      replace: true,
      state: {
        message: result.ok
          ? "You have been logged out."
          : "Your local session was cleared. Please login again.",
      },
    });
  }

  return (
    <div className="logout-action">
      <Button
        disabled={logoutMutation.isPending}
        fullWidth={fullWidth}
        onClick={handleLogout}
        type="button"
      >
        {logoutMutation.isPending ? "Logging out..." : "Logout"}
      </Button>

      {logoutError ? (
        <p className="logout-error" role="alert">
          {logoutError}
        </p>
      ) : null}
    </div>
  );
}