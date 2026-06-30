import { authService } from "./auth-service";
import { useAuthStore } from "./auth-store";

export function useAuth() {
  const session = useAuthStore((state) => state.session);
  const isLoading = useAuthStore((state) => state.isLoading);

  return {
    session,
    isLoading,

    isAuthenticated: session !== null,

    register: authService.register.bind(authService),

    login: authService.login.bind(authService),

    logout: authService.logout.bind(authService),

    resetPassword:
      authService.resetPassword.bind(authService),

    deleteAccount:
      authService.deleteAccount.bind(authService),

    restoreSession:
      authService.restoreSession.bind(authService),
  };
}
