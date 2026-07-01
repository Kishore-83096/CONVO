import { createContext } from "react";

import type { SaveSessionInput } from "../../shared/storage/authTokenStore";
import type { StoredCurrentUser } from "../../shared/storage/db";

export type AuthContextValue = {
  user: StoredCurrentUser | null;
  isBootstrapping: boolean;
  saveSession: (session: SaveSessionInput) => Promise<void>;
  clearSession: () => Promise<void>;
  refreshSession: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);