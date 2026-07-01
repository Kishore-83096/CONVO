import {
  openFrontendDatabase,
  type StoredAuthToken,
  type StoredCurrentUser,
} from "./db";

export type SaveSessionInput = {
  accessToken: string;
  tokenType: "Bearer";
  expiresAt: string;
  user: {
    id: string;
    full_name: string;
    username: string;
    email: string;
    contact_number: string;
  };
};

export async function saveAuthSession(input: SaveSessionInput): Promise<void> {
  const database = await openFrontendDatabase();
  const savedAt = new Date().toISOString();

  const authToken: StoredAuthToken = {
    id: "current",
    accessToken: input.accessToken,
    tokenType: input.tokenType,
    expiresAt: input.expiresAt,
    savedAt,
  };

  const currentUser: StoredCurrentUser = {
    id: "me",
    userId: input.user.id,
    fullName: input.user.full_name,
    username: input.user.username,
    email: input.user.email,
    contactNumber: input.user.contact_number,
    savedAt,
  };

  const transaction = database.transaction(
    ["authTokens", "currentUser"],
    "readwrite",
  );

  await Promise.all([
    transaction.objectStore("authTokens").put(authToken),
    transaction.objectStore("currentUser").put(currentUser),
  ]);

  await transaction.done;
}

export async function getCurrentAuthToken(): Promise<StoredAuthToken | null> {
  const database = await openFrontendDatabase();
  const token = await database.get("authTokens", "current");

  if (!token) {
    return null;
  }

  const expiresAtTime = new Date(token.expiresAt).getTime();

  if (Number.isFinite(expiresAtTime) && expiresAtTime <= Date.now()) {
    await clearAuthSession();
    return null;
  }

  return token;
}

export async function getAccessToken(): Promise<string | null> {
  const token = await getCurrentAuthToken();

  return token?.accessToken ?? null;
}

export async function getCurrentUser(): Promise<StoredCurrentUser | null> {
  const database = await openFrontendDatabase();
  const user = await database.get("currentUser", "me");

  return user ?? null;
}

export async function clearAuthSession(): Promise<void> {
  const database = await openFrontendDatabase();

  const transaction = database.transaction(
    ["authTokens", "currentUser"],
    "readwrite",
  );

  await Promise.all([
    transaction.objectStore("authTokens").delete("current"),
    transaction.objectStore("currentUser").delete("me"),
  ]);

  await transaction.done;
}