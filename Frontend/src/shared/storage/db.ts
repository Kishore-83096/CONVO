import { openDB, type DBSchema, type IDBPDatabase } from "idb";

export type StoredAuthToken = {
  id: "current";
  accessToken: string;
  tokenType: "Bearer";
  expiresAt: string;
  savedAt: string;
};

export type StoredCurrentUser = {
  id: "me";
  userId: string;
  fullName: string;
  username: string;
  email: string;
  contactNumber: string;
  savedAt: string;
};

export type StoredRealtimeTicket = {
  ticket: string;
  deviceId: string;
  expiresAt: string;
  savedAt: string;
};

type FrontendSecureDatabase = DBSchema & {
  authTokens: {
    key: "current";
    value: StoredAuthToken;
  };
  currentUser: {
    key: "me";
    value: StoredCurrentUser;
  };
  realtimeTickets: {
    key: string;
    value: StoredRealtimeTicket;
    indexes: {
      expiresAt: string;
      deviceId: string;
    };
  };
  schemaMigrations: {
    key: number;
    value: {
      version: number;
      appliedAt: string;
    };
  };
};

const DATABASE_NAME = "frontend_secure_client_db";
const DATABASE_VERSION = 1;

let databasePromise: Promise<IDBPDatabase<FrontendSecureDatabase>> | null = null;

export function openFrontendDatabase(): Promise<
  IDBPDatabase<FrontendSecureDatabase>
> {
  if (!databasePromise) {
    databasePromise = openDB<FrontendSecureDatabase>(
      DATABASE_NAME,
      DATABASE_VERSION,
      {
        upgrade(database) {
          if (!database.objectStoreNames.contains("authTokens")) {
            database.createObjectStore("authTokens", {
              keyPath: "id",
            });
          }

          if (!database.objectStoreNames.contains("currentUser")) {
            database.createObjectStore("currentUser", {
              keyPath: "id",
            });
          }

          if (!database.objectStoreNames.contains("realtimeTickets")) {
            const realtimeTicketStore = database.createObjectStore(
              "realtimeTickets",
              {
                keyPath: "ticket",
              },
            );

            realtimeTicketStore.createIndex("expiresAt", "expiresAt");
            realtimeTicketStore.createIndex("deviceId", "deviceId");
          }

          if (!database.objectStoreNames.contains("schemaMigrations")) {
            database.createObjectStore("schemaMigrations", {
              keyPath: "version",
            });
          }
        },
      },
    );
  }

  return databasePromise;
}

export async function clearFrontendDatabase(): Promise<void> {
  const database = await openFrontendDatabase();

  const transaction = database.transaction(
    ["authTokens", "currentUser", "realtimeTickets"],
    "readwrite",
  );

  await Promise.all([
    transaction.objectStore("authTokens").clear(),
    transaction.objectStore("currentUser").clear(),
    transaction.objectStore("realtimeTickets").clear(),
    transaction.done,
  ]);
}