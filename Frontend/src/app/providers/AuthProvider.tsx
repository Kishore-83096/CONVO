import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { configureAuthTokenReader } from "../../shared/api/authTokenBridge";
import {
  clearAuthSession,
  getAccessToken,
  getCurrentUser,
  type SaveSessionInput,
  saveAuthSession,
} from "../../shared/storage/authTokenStore";
import type { StoredCurrentUser } from "../../shared/storage/db";
import { AuthContext, type AuthContextValue } from "./authContext";

type AuthProviderProps = {
  children: ReactNode;
};

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<StoredCurrentUser | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  const refreshSession = useCallback(async (): Promise<void> => {
    const currentUser = await getCurrentUser();
    setUser(currentUser);
  }, []);

  const saveSession = useCallback(
    async (session: SaveSessionInput): Promise<void> => {
      await saveAuthSession(session);
      await refreshSession();
    },
    [refreshSession],
  );

  const clearSession = useCallback(async (): Promise<void> => {
    await clearAuthSession();
    setUser(null);
  }, []);

  useEffect(() => {
    configureAuthTokenReader(getAccessToken);

    async function bootstrapAuth() {
      try {
        await refreshSession();
      } finally {
        setIsBootstrapping(false);
      }
    }

    void bootstrapAuth();
  }, [refreshSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isBootstrapping,
      saveSession,
      clearSession,
      refreshSession,
    }),
    [user, isBootstrapping, saveSession, clearSession, refreshSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}