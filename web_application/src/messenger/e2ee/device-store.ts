import type { RegisterDeviceRequest } from "@/messenger/api/messenger-api.types"

const databaseName = "myna-messenger-e2ee"
const databaseVersion = 1
const deviceStoreName = "local-device"
const deviceStateKey = "primary"

interface StoredOneTimePreKey {
  key_id: number
  private_key_jwk: JsonWebKey
  public_key: string
  created_at: string
}

export interface StoredLocalDeviceState {
  id: typeof deviceStateKey
  registration_request: RegisterDeviceRequest
  identity_agreement_private_jwk: JsonWebKey
  identity_signing_private_jwk: JsonWebKey
  signed_prekey_private_jwk: JsonWebKey
  one_time_prekeys: StoredOneTimePreKey[]
  created_at: string
  updated_at: string
}

function openDatabase() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(databaseName, databaseVersion)

    request.onupgradeneeded = () => {
      const database = request.result

      if (!database.objectStoreNames.contains(deviceStoreName)) {
        database.createObjectStore(deviceStoreName, {
          keyPath: "id",
        })
      }
    }

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

async function withDeviceStore<T>(
  mode: IDBTransactionMode,
  action: (store: IDBObjectStore) => IDBRequest<T>,
) {
  const database = await openDatabase()

  return new Promise<T>((resolve, reject) => {
    const transaction = database.transaction(deviceStoreName, mode)
    const store = transaction.objectStore(deviceStoreName)
    const request = action(store)

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
    transaction.oncomplete = () => database.close()
    transaction.onerror = () => {
      database.close()
      reject(transaction.error)
    }
  })
}

export async function getStoredLocalDeviceState() {
  const state = await withDeviceStore<StoredLocalDeviceState | undefined>(
    "readonly",
    (store) => store.get(deviceStateKey),
  )

  return state ?? null
}

export async function saveStoredLocalDeviceState(
  state: Omit<StoredLocalDeviceState, "id" | "created_at" | "updated_at">
    & Partial<Pick<StoredLocalDeviceState, "created_at">>,
) {
  const now = new Date().toISOString()
  const existing = await getStoredLocalDeviceState()
  const nextState: StoredLocalDeviceState = {
    ...state,
    id: deviceStateKey,
    created_at: state.created_at ?? existing?.created_at ?? now,
    updated_at: now,
  }

  await withDeviceStore<IDBValidKey>("readwrite", (store) => store.put(nextState))

  return nextState
}

export async function addStoredOneTimePreKeys(
  prekeys: StoredOneTimePreKey[],
) {
  const state = await getStoredLocalDeviceState()

  if (!state) {
    return
  }

  const prekeysById = new Map(
    state.one_time_prekeys.map((prekey) => [prekey.key_id, prekey]),
  )

  for (const prekey of prekeys) {
    prekeysById.set(prekey.key_id, prekey)
  }

  await saveStoredLocalDeviceState({
    ...state,
    one_time_prekeys: Array.from(prekeysById.values()).sort(
      (first, second) => first.key_id - second.key_id,
    ),
  })
}

export async function deleteStoredLocalDeviceState() {
  await withDeviceStore<undefined>(
    "readwrite",
    (store) => store.delete(deviceStateKey),
  )
}
