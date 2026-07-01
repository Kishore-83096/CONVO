import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../../app/providers/useAuth";
import { Button } from "../../../shared/ui/Button";
import { useLogoutUser } from "../hooks";

type LogoutButtonProps = {
  fullWidth?: boolean;
  iconOnly?: boolean;
};

export function LogoutButton({
  fullWidth = false,
  iconOnly = false,
}: LogoutButtonProps) {
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
        aria-label={iconOnly ? "Logout" : undefined}
        disabled={logoutMutation.isPending}
        fullWidth={iconOnly ? false : fullWidth}
        className={iconOnly ? "logout-icon-button" : ""}
        onClick={handleLogout}
        type="button"
      >
        {iconOnly ? (
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M10 6H6A2 2 0 0 0 4 8V16A2 2 0 0 0 6 18H10" />
            <path d="M14 8L18 12L14 16" />
            <path d="M18 12H9" />
          </svg>
        ) : logoutMutation.isPending ? (
          "Logging out..."
        ) : (
          "Logout"
        )}
      </Button>

      {logoutError ? (
        <p className="logout-error" role="alert">
          {logoutError}
        </p>
      ) : null}
    </div>
  );
}
