# Myna Messenger Frontend Agent Implementation Guide

**Generated from uploaded backend zip:** `messenger(2).zip`  
**Backend service:** Django 5.2 + Django REST Framework  
**Frontend target:** React + TypeScript + Vite  
**Current transport:** REST only  
**Phase 13:** WebSockets are not implemented yet  
**Phase 14:** Not implemented yet; do not build UI logic that depends on it  
**Security rule:** strict end-to-end encryption. The frontend encrypts/decrypts. The backend stores ciphertext, public keys, encrypted key envelopes, encrypted recovery bundles, and routing metadata only.

---

## 0. Agent rules

This file is written for an AI coding agent that must build the frontend for the existing backend.

Follow these rules exactly:

1. **Do not send plaintext message text, attachment bytes, attachment filenames, attachment captions, private keys, session keys, sender-chain keys, recovery secrets, or raw message keys to the backend.**
2. **Do not invent backend endpoints.** Use only the REST endpoints documented here.
3. **Do not use WebSockets yet.** Phase 13 is not developed. Use polling/refresh/reconciliation through REST.
4. **Do not create a second non-E2EE message path.** Every message and attachment must be encrypted before upload/send.
5. **Do not place secret values inside metadata.** Metadata can contain algorithm names, nonce values, public key IDs, versions, public ratchet headers, hashes, and protocol labels only.
6. **All protected requests use the Identity-service JWT access token:**

```http
Authorization: Bearer <access-token>
Content-Type: application/json
```

7. The authenticated user ID is always taken from the JWT `sub` claim. Never send an owner/sender override field except where the API explicitly requires routing IDs such as `recipient_user_id`, `sender_device_id`, or `member_user_ids`.
8. Treat the Messenger backend as untrusted storage. Keep all private cryptographic material in IndexedDB or secure local device storage, and perform crypto in a Web Worker.

---

## 1. Environment variables

Create these frontend variables:

```env
VITE_IDENTITY_API_BASE_URL=http://localhost:5000/api/v1
VITE_MESSENGER_API_BASE_URL=http://localhost:8000/api/v1
VITE_MESSENGER_WS_BASE_URL=ws://localhost:8000
```

For production:

```env
VITE_IDENTITY_API_BASE_URL=https://<identity-host>/api/v1
VITE_MESSENGER_API_BASE_URL=https://<messenger-host>/api/v1
VITE_MESSENGER_WS_BASE_URL=wss://<messenger-host>
```

Normalize trailing slashes once:

```ts
const apiBase = import.meta.env.VITE_MESSENGER_API_BASE_URL.replace(/\/+$/, "");
```

Do not use `VITE_MESSENGER_WS_BASE_URL` until the backend WebSocket phase exists.

---

## 2. Common backend response shapes

Most Messenger APIs return:

```ts
export type ApiSuccess<T> = {
  success: true;
  message: string;
  data: T;
};

export type ApiFailure = {
  success: false;
  message: string;
  errors?: Record<string, string[]> | unknown;
};
```

Validation errors usually look like:

```json
{
  "success": false,
  "message": "Validation failed.",
  "errors": {
    "field_name": ["Error message."]
  }
}
```

Some auth errors from DRF can be plain:

```json
{
  "detail": "Authentication credentials were not provided."
}
```

Frontend API client requirements:

- Preserve HTTP status.
- Preserve backend `message`.
- Preserve field `errors`.
- On `401`, clear Identity session and lock/clear in-memory private keys.
- Do **not** auto-delete encrypted local IndexedDB data on `401`; only lock it.

---

## 3. Cryptography frontend contract

### 3.1 Required libraries

Use a dedicated crypto layer. Recommended frontend primitives:

- `libsodium-wrappers-sumo` for X25519, XChaCha20-Poly1305, Ed25519 signing, sealed boxes, random bytes, and base64 helpers.
- A dedicated Web Worker for all encryption/decryption.
- IndexedDB for encrypted local state and non-exportable app state references.

Never perform cryptographic operations directly inside React components.

---

### 3.2 Device keys

Every logged-in browser/device must create and persist:

```ts
type LocalDeviceSecretState = {
  deviceId: string;              // UUID generated client-side
  registrationId: number;        // Signal-style positive integer
  identityKeyPair: X25519KeyPair;
  signedPrekey: {
    keyId: number;
    keyPair: X25519KeyPair;
    signatureByIdentityKey: string; // base64
  };
  oneTimePrekeys: Array<{
    keyId: number;
    keyPair: X25519KeyPair;
  }>;
  pairwiseSessions: Record<string, unknown>; // keyed by user/device/session
  groupSenderKeys: Record<string, unknown>;  // keyed by group/epoch/device
  recoveryPrivateKey?: X25519PrivateKey;     // only while recovery is unlocked
};
```

Upload only public material:

- `identity_key_public`
- `signed_prekey_public`
- `signed_prekey_signature`
- one-time-prekey public keys

Keep private keys local.

---

### 3.3 Direct message encryption

For every direct message:

1. Build a plaintext JSON object locally:

```ts
type PlainDirectMessage = {
  kind: "text" | "image" | "video" | "audio" | "file" | "location" | "contact" | "edit" | "delete" | "reaction" | "system";
  body?: string;
  attachments?: EncryptedAttachmentPlainReference[];
  location?: unknown;
  contact?: unknown;
  event?: unknown;
  createdAtClient: string;
};
```

2. Generate a random 32-byte message content key.
3. Encrypt the plaintext JSON using **XChaCha20-Poly1305**.
4. Send the base64 ciphertext as `encrypted_payload`.
5. Send public cryptographic metadata only:

```json
{
  "algorithm": "xchacha20poly1305",
  "nonce": "BASE64_24_BYTE_NONCE",
  "content_format": "myna-direct-message-json-v1"
}
```

6. Wrap the message content key for every required active device:
   - recipient devices: `protocol = "double_ratchet"`
   - sender's own active devices: `protocol = "device_sync"`

Backend validation requires one envelope for **every active device belonging to the sender and the recipient**. The recipient device list comes from `POST /e2ee/prekey-bundles/claim/`. The current backend does **not** expose a general own-device list endpoint, so the frontend must not invent one. For multi-device sender accounts, store/know own active devices locally or expect the backend to reject missing envelopes with a clear error until a device-list API exists.

---

### 3.4 Direct device key-envelope algorithms

For recipient devices, use a Signal-style X3DH + Double Ratchet session:

```json
{
  "recipient_device_id": "UUID",
  "protocol": "double_ratchet",
  "session_reference": "recipient-user-id:recipient-device-id:v1",
  "wrapped_message_key": "BASE64_ENCRYPTED_32_BYTE_MESSAGE_KEY",
  "key_wrap_metadata": {
    "algorithm": "double-ratchet-v1",
    "nonce": "BASE64_NONCE_OR_RATCHET_HEADER_NONCE",
    "ratchet_public_key": "BASE64_PUBLIC_RATCHET_KEY",
    "message_number": 1,
    "previous_chain_length": 0
  },
  "envelope_version": 1
}
```

For sender's own devices, use device-sync wrapping:

```json
{
  "recipient_device_id": "UUID_OF_OWN_DEVICE",
  "protocol": "device_sync",
  "session_reference": "device-sync:<own-device-id>:<message-id>",
  "wrapped_message_key": "BASE64_ENCRYPTED_32_BYTE_MESSAGE_KEY",
  "key_wrap_metadata": {
    "algorithm": "device-sync-v1",
    "nonce": "BASE64_24_BYTE_NONCE"
  },
  "envelope_version": 1
}
```

The backend validates `protocol` strictly for direct sends:

- same user as sender: must be `device_sync`
- other user: must be `double_ratchet`

---

### 3.5 Recovery encryption

Recovery is optional per user, but if a participant has active recovery enabled, the send APIs require recovery envelopes.

Recovery setup creates:

- a recovery public/private keypair on the client
- a human recovery key and/or WebAuthn PRF-derived wrapping key
- an encrypted recovery private key bundle stored on the server

Recovery bundle encryption metadata must use:

```json
{
  "algorithm": "xchacha20poly1305-ietf",
  "nonce": "BASE64_24_BYTE_NONCE",
  "unlock_method": "recovery_key" 
}
```

Supported `unlock_method` values:

- `recovery_key`
- `webauthn_prf`
- `recovery_key_and_webauthn_prf`

Recovery message-key envelope metadata must use:

```json
{
  "algorithm": "recovery-box-v1",
  "nonce": "BASE64_24_BYTE_NONCE"
}
```

Use the recovery public key to encrypt/wrap the same 32-byte message content key for each recovery owner. The server stores this as `MessageRecoveryEnvelope`. The server never sees the plaintext message key.

---

### 3.6 Attachment encryption

Attachments are encrypted before upload/storage.

Frontend flow:

1. Generate a random 32-byte attachment key.
2. Encrypt the file bytes locally using XChaCha20-Poly1305, preferably chunked for large files.
3. Hash encrypted bytes using SHA-256 hex.
4. Initiate attachment metadata with the backend.
5. Upload encrypted bytes to the storage provider using the returned `storage_key` or your storage adapter.
6. Complete the attachment using ciphertext SHA-256 and ciphertext size.
7. Include attachment reference and attachment key inside the encrypted message plaintext, not backend metadata.

Do **not** send plaintext filename, caption, exact MIME type, or attachment key outside `encrypted_payload` unless you intentionally accept that metadata leakage.

Recommended encrypted message plaintext reference:

```json
{
  "kind": "file",
  "attachments": [
    {
      "attachment_id": "UUID",
      "name": "report.pdf",
      "mime_type": "application/pdf",
      "ciphertext_size": 123456,
      "key": "BASE64_32_BYTE_ATTACHMENT_KEY",
      "nonce": "BASE64_24_BYTE_NONCE",
      "algorithm": "xchacha20poly1305",
      "sha256": "HEX_SHA256_OF_CIPHERTEXT"
    }
  ]
}
```

Only encrypted metadata is visible to recipients after they decrypt the message.

---

### 3.7 Group sender-key encryption

Groups use sender-key style encryption.

For every group, epoch, user device:

1. Get current epoch.
2. Get group device roster for the epoch.
3. The sender device creates a group sender key locally.
4. Register only the public signing key and sender key public ID.
5. Encrypt/distribute the sender key to every required recipient device using pairwise E2EE.
6. Send group messages using `algorithm: "group-sender-key-v1"`.
7. Sign each group ciphertext/event using Ed25519.

Never upload:

- raw group sender-chain key
- private signing key
- message key
- ratchet state
- plaintext

Group send requires sender-key distribution coverage for all required active devices except the sender device.

---

## 4. Frontend modules to build

Recommended structure:

```text
src/
  config/env.ts
  lib/api/httpClient.ts
  lib/api/messengerApi.ts
  lib/crypto/cryptoWorker.ts
  lib/crypto/workerProtocol.ts
  lib/storage/indexedDb.ts
  features/auth/sessionStore.ts
  features/e2ee/deviceStore.ts
  features/e2ee/deviceSetup.ts
  features/e2ee/prekeys.ts
  features/recovery/recoveryStore.ts
  features/recovery/recoveryFlows.ts
  features/messages/directMessageApi.ts
  features/messages/directCrypto.ts
  features/messages/messageCache.ts
  features/attachments/attachmentCrypto.ts
  features/attachments/attachmentApi.ts
  features/groups/groupApi.ts
  features/groups/groupCrypto.ts
  features/groups/senderKeyDistribution.ts
  features/receipts/receiptApi.ts
  pages/MessengerLayout.tsx
  pages/DeviceSetupPage.tsx
  pages/RecoverySetupPage.tsx
  pages/ChatRoomPage.tsx
  pages/GroupRoomPage.tsx
```

Minimum UI screens:

- Device setup screen
- Recovery setup/unlock screen
- Room list
- Direct chat room
- Group list/create/update
- Group member management
- Group sender-key setup status
- Attachment picker/upload progress
- Recovery coverage/backfill screen
- Settings/security screen

---

## 5. Endpoint inventory

Base path is `VITE_MESSENGER_API_BASE_URL`, normally ending with `/api/v1`.

### Public / auth diagnostic

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/` | Public health check |
| GET | `/auth/whoami/` | Validate JWT integration and return limited token info |

### E2EE device and recovery

| Method | Path | Purpose |
|---|---|---|
| POST | `/e2ee/devices/register/` | Register or update current device public key bundle |
| POST | `/e2ee/devices/{device_id}/prekeys/` | Upload one-time prekeys for current user's device |
| POST | `/e2ee/prekey-bundles/claim/` | Claim all active recipient device prekey bundles |
| POST | `/e2ee/recovery/setup/` | Create encrypted recovery bundle |
| GET | `/e2ee/recovery/status/` | Get recovery status |
| GET | `/e2ee/recovery/bundle/` | Download own encrypted recovery bundle |
| POST | `/e2ee/recovery/public-keys/resolve/` | Resolve active recovery public keys for users |
| POST | `/e2ee/recovery/rotate/` | Rotate recovery bundle and rewrap recovery envelopes |
| DELETE | `/e2ee/recovery/` | Disable recovery and delete recovery envelopes |

### Direct rooms/messages/recovery/attachments/receipts

| Method | Path | Purpose |
|---|---|---|
| POST | `/messages/direct/` | Store encrypted direct message |
| GET | `/messages/rooms/` | List rooms through messages app |
| GET | `/rooms/` | List rooms through root route; same room-list view |
| GET | `/messages/rooms/{room_id}/history/?device_id=...` | Direct/device-specific encrypted history |
| GET | `/rooms/{room_id}/history/?device_id=...` | Same direct/device-specific history view |
| GET | `/messages/recovery-history/` | Get recovery-readable encrypted history |
| POST | `/messages/recovery/rewrap/` | Create device-sync envelopes after recovery unlock |
| GET | `/messages/recovery/backfill/candidates/?device_id=...` | Find messages missing recovery envelope |
| POST | `/messages/recovery/backfill/` | Backfill recovery envelopes |
| GET | `/messages/recovery/coverage/` | Recovery coverage and stale envelope status |
| POST | `/messages/receipts/delivered/` | Mark messages delivered for current device |
| POST | `/messages/receipts/read/` | Mark group read-through receipts |
| GET | `/messages/{message_id}/receipts/` | Receipt summary |
| POST | `/messages/attachments/initiate/` | Initiate encrypted attachment metadata |
| POST | `/messages/attachments/{attachment_id}/complete/` | Complete encrypted attachment metadata |
| GET | `/messages/attachments/{attachment_id}/download/?device_id=...` | Get encrypted attachment storage metadata |
| DELETE | `/messages/attachments/{attachment_id}/` | Mark encrypted attachment deleted |

### Groups and group E2EE

| Method | Path | Purpose |
|---|---|---|
| GET | `/groups/` | List groups for current user |
| POST | `/groups/` | Create group |
| GET | `/groups/{group_id}/` | Group details |
| PATCH | `/groups/{group_id}/` | Update group profile/settings |
| GET | `/groups/{group_id}/members/` | List group members |
| POST | `/groups/{group_id}/members/` | Add members |
| DELETE | `/groups/{group_id}/members/{user_id}/` | Remove member |
| PATCH | `/groups/{group_id}/members/{user_id}/role/` | Change member role |
| POST | `/groups/{group_id}/leave/` | Leave group |
| POST | `/groups/{group_id}/transfer-ownership/` | Transfer ownership |
| POST | `/groups/{group_id}/members/{user_id}/ban/` | Ban member |
| POST | `/groups/{group_id}/members/{user_id}/unban/` | Unban member |
| GET | `/groups/{group_id}/epochs/current/` | Current group encryption epoch |
| GET | `/groups/{group_id}/epochs/` | List group epochs |
| POST | `/groups/{group_id}/epochs/rotate/` | Rotate epoch |
| GET | `/groups/{group_id}/devices/?epoch_number=...` | Active member device roster for epoch |
| POST | `/groups/{group_id}/sender-keys/register/` | Register sender key public metadata |
| GET | `/groups/{group_id}/sender-keys/mine/?device_id=...` | Lookup sender key for current device |
| DELETE | `/groups/{group_id}/sender-keys/{sender_key_id}/` | Revoke sender key |
| POST | `/groups/{group_id}/sender-keys/{sender_key_id}/distributions/` | Store sender-key distributions |
| GET | `/groups/{group_id}/sender-keys/{sender_key_id}/pending/` | Sender-key distribution coverage |
| GET | `/groups/{group_id}/sender-key-distributions/inbox/?device_id=...` | Recipient device distribution inbox |
| POST | `/groups/{group_id}/sender-key-distributions/acknowledge/` | Acknowledge distributions |
| GET | `/groups/{group_id}/recovery-recipients/` | Active recovery recipients for group |
| POST | `/messages/group/` | Send encrypted group message |
| GET | `/messages/groups/{group_id}/history/?device_id=...` | Group encrypted history |

---

## 6. Detailed API contracts

### 6.1 `GET /health/`

Auth: none.

Response:

```json
{
  "message": "Messenger service is running.",
  "service": "messenger-service",
  "environment": "local"
}
```

---

### 6.2 `GET /auth/whoami/`

Auth: Bearer required.

Response:

```json
{
  "authenticated": true,
  "user_id": "1",
  "token_type": "access",
  "expires_at": 1790000000
}
```

Use only as diagnostic/integration check.

---

### 6.3 `POST /e2ee/devices/register/`

Registers current device public cryptographic bundle.

Request:

```json
{
  "device_id": "11111111-1111-4111-8111-111111111111",
  "device_name": "Chrome on Windows",
  "platform": "web",
  "registration_id": 10001,
  "identity_key_public": "BASE64_X25519_IDENTITY_PUBLIC",
  "signed_prekey_id": 1,
  "signed_prekey_public": "BASE64_X25519_SIGNED_PREKEY_PUBLIC",
  "signed_prekey_signature": "BASE64_SIGNATURE_BY_IDENTITY_KEY",
  "key_algorithm": "curve25519",
  "key_bundle_version": 1,
  "one_time_prekeys": [
    {
      "key_id": 1,
      "public_key": "BASE64_X25519_ONE_TIME_PREKEY_PUBLIC"
    }
  ]
}
```

Valid `platform` values:

- `android`
- `ios`
- `web`
- `desktop`
- `other`

Limits:

- max 200 one-time prekeys per request
- key text max 4096 chars
- key IDs positive integers
- duplicate prekey IDs rejected

Response `201` on first registration, `200` on idempotent/update:

```json
{
  "success": true,
  "message": "Device registered successfully.",
  "data": {
    "device_id": "11111111-1111-4111-8111-111111111111",
    "user_id": "1",
    "device_created": true,
    "prekeys_created": 100,
    "prekeys_unchanged": 0
  }
}
```

Conflict behavior:

- Reusing same `device_id` with different identity key or registration ID returns `409`.
- Reusing same `signed_prekey_id` with different signed-prekey material returns `409`.
- Reusing same one-time-prekey `key_id` with different public key returns `409`.

Frontend rule: generate a new `device_id` if identity key changes.

---

### 6.4 `POST /e2ee/devices/{device_id}/prekeys/`

Uploads more one-time prekeys for an active owned device.

Request:

```json
{
  "one_time_prekeys": [
    {
      "key_id": 101,
      "public_key": "BASE64_X25519_ONE_TIME_PREKEY_PUBLIC"
    }
  ]
}
```

Response:

```json
{
  "success": true,
  "message": "One-time prekeys uploaded successfully.",
  "data": {
    "device_id": "11111111-1111-4111-8111-111111111111",
    "prekeys_created": 1,
    "prekeys_unchanged": 0
  }
}
```

Use when local one-time prekey stock is low. The backend currently has no prekey stock count endpoint, so the frontend should upload a safe batch during device setup and periodically after successful sends.

---

### 6.5 `POST /e2ee/prekey-bundles/claim/`

Claims active recipient device prekey bundles. This atomically marks one available one-time prekey per recipient device as claimed.

Request:

```json
{
  "recipient_user_id": "2"
}
```

Response:

```json
{
  "success": true,
  "message": "Recipient prekey bundles claimed.",
  "data": {
    "recipient_user_id": "2",
    "device_count": 1,
    "devices": [
      {
        "device_id": "22222222-2222-4222-8222-222222222222",
        "registration_id": 20001,
        "identity_key_public": "BASE64_IDENTITY_PUBLIC",
        "signed_prekey": {
          "key_id": 1,
          "public_key": "BASE64_SIGNED_PREKEY_PUBLIC",
          "signature": "BASE64_SIGNATURE"
        },
        "one_time_prekey": {
          "key_id": 10,
          "public_key": "BASE64_ONE_TIME_PREKEY_PUBLIC"
        },
        "key_algorithm": "curve25519",
        "key_bundle_version": 1
      }
    ]
  }
}
```

`one_time_prekey` may be `null`. The frontend must still be able to establish/update a session using the signed prekey path if your Signal-style design allows it.

Errors:

- `400` for self recipient or invalid user ID
- `404` if recipient has no active E2EE devices

---

### 6.6 `POST /messages/direct/`

Stores encrypted direct message and creates/reuses a direct room.

Request:

```json
{
  "recipient_user_id": "2",
  "sender_device_id": "11111111-1111-4111-8111-111111111111",
  "client_message_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "message_type": "text",
  "encrypted_payload": "BASE64_CIPHERTEXT",
  "encryption_metadata": {
    "algorithm": "xchacha20poly1305",
    "nonce": "BASE64_24_BYTE_NONCE",
    "content_format": "myna-direct-message-json-v1"
  },
  "encryption_version": 1,
  "reply_to_id": null,
  "client_sent_at": "2026-06-27T19:30:00Z",
  "envelopes": [
    {
      "recipient_device_id": "11111111-1111-4111-8111-111111111111",
      "protocol": "device_sync",
      "session_reference": "device-sync:11111111-1111-4111-8111-111111111111:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "wrapped_message_key": "BASE64_WRAPPED_MESSAGE_KEY_FOR_SENDER_DEVICE",
      "key_wrap_metadata": {
        "algorithm": "device-sync-v1",
        "nonce": "BASE64_24_BYTE_NONCE"
      },
      "envelope_version": 1
    },
    {
      "recipient_device_id": "22222222-2222-4222-8222-222222222222",
      "protocol": "double_ratchet",
      "session_reference": "2:22222222-2222-4222-8222-222222222222:v1",
      "wrapped_message_key": "BASE64_WRAPPED_MESSAGE_KEY_FOR_RECIPIENT_DEVICE",
      "key_wrap_metadata": {
        "algorithm": "double-ratchet-v1",
        "nonce": "BASE64_24_BYTE_NONCE"
      },
      "envelope_version": 1
    }
  ],
  "recovery_envelopes": [
    {
      "recovery_owner_user_id": "1",
      "recovery_key_version": 1,
      "wrapped_message_key": "BASE64_RECOVERY_WRAPPED_MESSAGE_KEY",
      "key_wrap_metadata": {
        "algorithm": "recovery-box-v1",
        "nonce": "BASE64_24_BYTE_NONCE"
      },
      "envelope_version": 1
    }
  ]
}
```

Valid `message_type` values:

- `text`
- `image`
- `video`
- `audio`
- `file`
- `location`
- `contact`
- `edit`
- `delete`
- `reaction`
- `system`

Required logic:

- `client_message_id` is generated by frontend before send and reused for retries.
- `envelopes` must include exactly one envelope per active sender+recipient device.
- `recovery_envelopes` must include exactly one envelope for every participant with active recovery.
- If no participant has active recovery, send `[]` or omit `recovery_envelopes`.

Response `201` on create, `200` on idempotent retry:

```json
{
  "success": true,
  "message": "Encrypted direct message stored successfully.",
  "data": {
    "room_id": "ROOM_UUID",
    "room_type": "direct",
    "room_created": true,
    "message_id": "MESSAGE_UUID",
    "client_message_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "message_created": true,
    "envelope_count": 2,
    "recovery_envelope_count": 1,
    "created_at": "2026-06-27T19:30:01Z"
  }
}
```

Conflict behavior:

- Reusing same `client_message_id` with different ciphertext, metadata, envelopes, recovery envelopes, or reply fields returns `409`.

---

### 6.7 `GET /rooms/` or `GET /messages/rooms/`

Lists active direct and group rooms for authenticated user.

Response:

```json
{
  "success": true,
  "message": "Rooms retrieved successfully.",
  "data": [
    {
      "id": "ROOM_UUID",
      "room_type": "direct",
      "name": "",
      "member_user_ids": ["1", "2"],
      "other_member_user_ids": ["2"],
      "group": null,
      "created_at": "...",
      "updated_at": "...",
      "last_message": {
        "id": "MESSAGE_UUID",
        "sender_user_id": "1",
        "message_type": "text",
        "created_at": "..."
      }
    },
    {
      "id": "GROUP_ROOM_UUID",
      "room_type": "group",
      "name": "Project Team",
      "member_user_ids": ["1", "2", "3"],
      "other_member_user_ids": ["2", "3"],
      "group": {
        "caller_role": "owner",
        "member_count": 3,
        "security_ready": false,
        "active_epoch_number": 1
      },
      "created_at": "...",
      "updated_at": "...",
      "last_message": null
    }
  ]
}
```

Frontend must get display names/avatars from the Identity/Profile service because Messenger only knows external user IDs.

---

### 6.8 `GET /rooms/{room_id}/history/?device_id={device_id}`

Also available at `/messages/rooms/{room_id}/history/?device_id=...`.

Returns messages that have a device envelope for the given owned device.

Query:

```text
device_id=11111111-1111-4111-8111-111111111111
page_size=50 optional, max 100
cursor=<DRF cursor> optional
```

Response:

```json
{
  "success": true,
  "message": "Encrypted message history retrieved successfully.",
  "data": {
    "room_id": "ROOM_UUID",
    "room_type": "direct",
    "device_id": "11111111-1111-4111-8111-111111111111",
    "next": null,
    "previous": null,
    "messages": [
      {
        "id": "MESSAGE_UUID",
        "room_id": "ROOM_UUID",
        "sender_user_id": "2",
        "sender_device_id": "22222222-2222-4222-8222-222222222222",
        "client_message_id": "CLIENT_MESSAGE_UUID",
        "message_type": "text",
        "encrypted_payload": "BASE64_CIPHERTEXT",
        "encryption_metadata": {
          "algorithm": "xchacha20poly1305",
          "nonce": "BASE64_NONCE"
        },
        "encryption_version": 1,
        "reply_to_id": null,
        "client_sent_at": "...",
        "created_at": "...",
        "device_envelope": {
          "recipient_user_id": "1",
          "recipient_device_id": "11111111-1111-4111-8111-111111111111",
          "protocol": "double_ratchet",
          "session_reference": "...",
          "wrapped_message_key": "BASE64_WRAPPED_MESSAGE_KEY",
          "key_wrap_metadata": {
            "algorithm": "double-ratchet-v1",
            "nonce": "BASE64_NONCE"
          },
          "envelope_version": 1
        }
      }
    ]
  }
}
```

Frontend decrypt flow:

1. Use `device_envelope.protocol` to unwrap message content key.
2. Use message `encryption_metadata.nonce` and unwrapped content key to decrypt `encrypted_payload`.
3. Never render undecryptable content as plaintext. Show “Unable to decrypt” with retry/recovery actions.

---

## 7. Recovery endpoint contracts

### 7.1 `POST /e2ee/recovery/setup/`

Request:

```json
{
  "recovery_public_key": "BASE64_RECOVERY_PUBLIC_KEY",
  "encrypted_recovery_private_key": "BASE64_ENCRYPTED_RECOVERY_PRIVATE_KEY",
  "encryption_metadata": {
    "algorithm": "xchacha20poly1305-ietf",
    "nonce": "BASE64_24_BYTE_NONCE",
    "unlock_method": "recovery_key_and_webauthn_prf",
    "kdf": "hkdf-sha256"
  }
}
```

Response:

```json
{
  "success": true,
  "message": "Encrypted recovery configured successfully.",
  "data": {
    "recovery_version": 1,
    "is_active": true,
    "created_at": "...",
    "updated_at": "...",
    "rotated_at": null
  }
}
```

Active recovery cannot be overwritten through setup; use rotate endpoint.

---

### 7.2 `GET /e2ee/recovery/status/`

Response:

```json
{
  "success": true,
  "message": "Encrypted recovery status retrieved successfully.",
  "data": {
    "configured": true,
    "is_active": true,
    "recovery_version": 1,
    "created_at": "...",
    "updated_at": "...",
    "rotated_at": null,
    "disabled_at": null
  }
}
```

---

### 7.3 `GET /e2ee/recovery/bundle/`

Downloads own encrypted recovery private-key bundle.

Response:

```json
{
  "success": true,
  "message": "Encrypted recovery bundle retrieved successfully.",
  "data": {
    "recovery_public_key": "BASE64_RECOVERY_PUBLIC_KEY",
    "encrypted_recovery_private_key": "BASE64_ENCRYPTED_RECOVERY_PRIVATE_KEY",
    "encryption_metadata": {
      "algorithm": "xchacha20poly1305-ietf",
      "nonce": "BASE64_24_BYTE_NONCE",
      "unlock_method": "recovery_key"
    },
    "recovery_version": 1,
    "is_active": true,
    "created_at": "...",
    "updated_at": "...",
    "rotated_at": null
  }
}
```

Frontend decrypts `encrypted_recovery_private_key` locally using recovery key/passkey PRF.

---

### 7.4 `POST /e2ee/recovery/public-keys/resolve/`

Resolve recovery public keys for multiple users.

Request:

```json
{
  "user_ids": ["1", "2"]
}
```

Limits:

- max 20 user IDs
- duplicates rejected

Response:

```json
{
  "success": true,
  "message": "Recovery public keys resolved successfully.",
  "data": {
    "public_keys": [
      {
        "user_id": "1",
        "recovery_public_key": "BASE64_PUBLIC_KEY",
        "recovery_version": 1,
        "updated_at": "..."
      }
    ]
  }
}
```

Use before sending direct messages if either participant may have recovery enabled. For groups, prefer `/groups/{group_id}/recovery-recipients/`.

---

### 7.5 `GET /messages/recovery-history/`

Returns messages recoverable by current user's active recovery bundle.

Response:

```json
{
  "success": true,
  "message": "Encrypted recovery history retrieved successfully.",
  "data": {
    "next": null,
    "previous": null,
    "messages": [
      {
        "id": "MESSAGE_UUID",
        "room_id": "ROOM_UUID",
        "sender_user_id": "2",
        "sender_device_id": "DEVICE_UUID",
        "client_message_id": "CLIENT_MESSAGE_UUID",
        "message_type": "text",
        "encrypted_payload": "BASE64_CIPHERTEXT",
        "encryption_metadata": {
          "algorithm": "xchacha20poly1305",
          "nonce": "BASE64_NONCE"
        },
        "encryption_version": 1,
        "reply_to_id": null,
        "client_sent_at": "...",
        "created_at": "...",
        "recovery_envelope": {
          "recovery_owner_user_id": "1",
          "recovery_key_version": 1,
          "wrapped_message_key": "BASE64_RECOVERY_WRAPPED_MESSAGE_KEY",
          "key_wrap_metadata": {
            "algorithm": "recovery-box-v1",
            "nonce": "BASE64_NONCE"
          },
          "envelope_version": 1,
          "created_at": "...",
          "updated_at": "..."
        }
      }
    ]
  }
}
```

New-device recovery flow:

1. Register new device.
2. Download recovery bundle.
3. User unlocks recovery private key locally.
4. Fetch recovery history.
5. Decrypt recovery envelope to get each message content key.
6. Decrypt message payload.
7. Rewrap recovered content keys for the new device using `/messages/recovery/rewrap/`.

---

### 7.6 `POST /messages/recovery/rewrap/`

Creates `device_sync` message-key envelopes for a new/recovered device after local recovery unlock.

Request:

```json
{
  "device_id": "NEW_DEVICE_UUID",
  "envelopes": [
    {
      "message_id": "MESSAGE_UUID",
      "wrapped_message_key": "BASE64_DEVICE_SYNC_WRAPPED_MESSAGE_KEY",
      "key_wrap_metadata": {
        "algorithm": "device-sync-v1",
        "nonce": "BASE64_24_BYTE_NONCE"
      },
      "envelope_version": 1
    }
  ]
}
```

Limits:

- max 100 envelopes
- duplicate message IDs rejected
- metadata algorithm must be `device-sync-v1`
- metadata requires non-empty `nonce`

Response:

```json
{
  "success": true,
  "message": "Recovered message keys were wrapped for the device successfully.",
  "data": {
    "device_id": "NEW_DEVICE_UUID",
    "created_count": 10,
    "existing_count": 0,
    "total_count": 10
  }
}
```

---

### 7.7 `GET /messages/recovery/backfill/candidates/?device_id={device_id}`

Finds messages that the current user can decrypt through a device envelope but that do not yet have a recovery envelope.

Response:

```json
{
  "success": true,
  "message": "Recovery backfill candidates retrieved successfully.",
  "data": {
    "device_id": "DEVICE_UUID",
    "recovery_key_version": 1,
    "next": null,
    "previous": null,
    "messages": [
      {
        "id": "MESSAGE_UUID",
        "room_id": "ROOM_UUID",
        "sender_user_id": "2",
        "sender_device_id": "DEVICE_UUID",
        "client_message_id": "CLIENT_MESSAGE_UUID",
        "message_type": "text",
        "encrypted_payload": "BASE64_CIPHERTEXT",
        "encryption_metadata": {},
        "encryption_version": 1,
        "reply_to_id": null,
        "client_sent_at": null,
        "created_at": "...",
        "device_envelope": {
          "recipient_user_id": "1",
          "recipient_device_id": "DEVICE_UUID",
          "protocol": "device_sync",
          "session_reference": "...",
          "wrapped_message_key": "BASE64_WRAPPED_KEY",
          "key_wrap_metadata": {},
          "envelope_version": 1,
          "created_at": "..."
        }
      }
    ]
  }
}
```

Frontend decrypts the device envelope locally, then wraps the content key for recovery.

---

### 7.8 `POST /messages/recovery/backfill/`

Request:

```json
{
  "device_id": "DEVICE_UUID",
  "recovery_key_version": 1,
  "envelopes": [
    {
      "message_id": "MESSAGE_UUID",
      "wrapped_message_key": "BASE64_RECOVERY_WRAPPED_MESSAGE_KEY",
      "key_wrap_metadata": {
        "algorithm": "recovery-box-v1",
        "nonce": "BASE64_24_BYTE_NONCE"
      },
      "envelope_version": 1
    }
  ]
}
```

Limits:

- max 100 envelopes
- metadata algorithm must be `recovery-box-v1`
- metadata requires non-empty `nonce`

Response:

```json
{
  "success": true,
  "message": "Recovery envelopes backfilled successfully.",
  "data": {
    "device_id": "DEVICE_UUID",
    "recovery_key_version": 1,
    "created_count": 10,
    "existing_count": 0,
    "total_count": 10
  }
}
```

---

### 7.9 `GET /messages/recovery/coverage/`

Response:

```json
{
  "success": true,
  "message": "Recovery coverage retrieved successfully.",
  "data": {
    "recovery_version": 1,
    "total_eligible_messages": 120,
    "current_version_covered_messages": 100,
    "missing_recovery_envelopes": 15,
    "stale_recovery_envelopes": 5,
    "coverage_percent": 83.33,
    "is_complete": false,
    "active_devices": [
      {
        "device_id": "DEVICE_UUID",
        "device_name": "Chrome on Windows",
        "platform": "web",
        "backfill_candidate_count": 15
      }
    ]
  }
}
```

Use this for Recovery Settings UI.

---

### 7.10 `POST /e2ee/recovery/rotate/`

Rotates recovery bundle and optionally replaces recovery envelopes for existing messages.

Request:

```json
{
  "current_recovery_version": 1,
  "recovery_public_key": "BASE64_NEW_RECOVERY_PUBLIC_KEY",
  "encrypted_recovery_private_key": "BASE64_NEW_ENCRYPTED_RECOVERY_PRIVATE_KEY",
  "encryption_metadata": {
    "algorithm": "xchacha20poly1305-ietf",
    "nonce": "BASE64_24_BYTE_NONCE",
    "unlock_method": "recovery_key"
  },
  "recovery_envelopes": [
    {
      "message_id": "MESSAGE_UUID",
      "wrapped_message_key": "BASE64_NEW_RECOVERY_WRAPPED_MESSAGE_KEY",
      "key_wrap_metadata": {
        "algorithm": "recovery-box-v1",
        "nonce": "BASE64_24_BYTE_NONCE"
      },
      "envelope_version": 1
    }
  ]
}
```

Response:

```json
{
  "success": true,
  "message": "Encrypted recovery rotated successfully.",
  "data": {
    "recovery_version": 2,
    "rotated_envelope_count": 120,
    "rotation_applied": true,
    "rotated_at": "..."
  }
}
```

Conflict cases:

- stale `current_recovery_version`
- missing envelope coverage for eligible messages
- duplicate message IDs
- idempotent retry with different data

---

### 7.11 `DELETE /e2ee/recovery/`

Disables recovery and deletes recovery envelopes.

Response:

```json
{
  "success": true,
  "message": "Encrypted recovery disabled successfully.",
  "data": {
    "bundle_deleted": true,
    "deleted_recovery_envelope_count": 120
  }
}
```

Frontend must warn that cloud recovery of old history will no longer work unless messages still have device envelopes on active devices.

---

## 8. Attachment endpoint contracts

### 8.1 `POST /messages/attachments/initiate/`

Request:

```json
{
  "device_id": "DEVICE_UUID",
  "storage_provider": "cloudinary",
  "storage_key": "encrypted-attachments/1/generated-id",
  "media_category": "file",
  "expires_at": null
}
```

Fields:

- `storage_provider`: `cloudinary`, `s3`, `local`; default `cloudinary`
- `storage_key`: optional; if blank backend generates `encrypted-attachments/{user_id}/{uuid}`
- `media_category`: `image`, `video`, `audio`, `file`; default `file`
- `expires_at`: optional ISO datetime

Response `201`:

```json
{
  "success": true,
  "message": "Encrypted attachment initiated successfully.",
  "data": {
    "id": "ATTACHMENT_UUID",
    "uploader_user_id": "1",
    "uploader_device_id": "DEVICE_UUID",
    "storage_provider": "cloudinary",
    "storage_key": "encrypted-attachments/1/generated-id",
    "ciphertext_sha256": "",
    "ciphertext_size": 0,
    "media_category": "file",
    "upload_status": "initiated",
    "created_at": "...",
    "completed_at": null,
    "expires_at": null
  }
}
```

Do not include secret words in `storage_key`: `plaintext`, `private`, `secret`, `raw_key`, `attachment_key`.

---

### 8.2 `POST /messages/attachments/{attachment_id}/complete/`

Request:

```json
{
  "device_id": "DEVICE_UUID",
  "ciphertext_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "ciphertext_size": 4096
}
```

Response:

```json
{
  "success": true,
  "message": "Encrypted attachment completed successfully.",
  "data": {
    "id": "ATTACHMENT_UUID",
    "uploader_user_id": "1",
    "uploader_device_id": "DEVICE_UUID",
    "storage_provider": "cloudinary",
    "storage_key": "encrypted-attachments/1/generated-id",
    "ciphertext_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "ciphertext_size": 4096,
    "media_category": "file",
    "upload_status": "completed",
    "created_at": "...",
    "completed_at": "...",
    "expires_at": null
  }
}
```

Only the upload device can complete the attachment.

---

### 8.3 `GET /messages/attachments/{attachment_id}/download/?device_id={device_id}`

Response:

```json
{
  "success": true,
  "message": "Encrypted attachment download metadata retrieved.",
  "data": {
    "id": "ATTACHMENT_UUID",
    "storage_provider": "cloudinary",
    "storage_key": "encrypted-attachments/1/generated-id",
    "ciphertext_sha256": "...",
    "ciphertext_size": 4096,
    "media_category": "file",
    "upload_status": "completed"
  }
}
```

Current backend allows only the uploader owner to retrieve by attachment ownership. Do not assume cross-user attachment download works from this endpoint unless backend is later updated. For message recipients, include enough storage metadata inside the encrypted message plaintext.

---

### 8.4 `DELETE /messages/attachments/{attachment_id}/`

Request body or query:

```json
{
  "device_id": "DEVICE_UUID"
}
```

Response:

```json
{
  "success": true,
  "message": "Encrypted attachment deleted successfully.",
  "data": {
    "id": "ATTACHMENT_UUID",
    "upload_status": "deleted"
  }
}
```

Delete is idempotent.

---

## 9. Receipt endpoint contracts

### 9.1 `POST /messages/receipts/delivered/`

Request:

```json
{
  "device_id": "DEVICE_UUID",
  "message_ids": ["MESSAGE_UUID"]
}
```

Limits:

- `message_ids` non-empty
- max 250 message IDs

Response:

```json
{
  "success": true,
  "message": "Delivered receipts stored successfully.",
  "data": {
    "updated_count": 1,
    "receipt_ids": ["RECEIPT_UUID"]
  }
}
```

The backend skips messages sent by the same user.

---

### 9.2 `POST /messages/receipts/read/`

Currently implemented for **group read-through**.

Request:

```json
{
  "device_id": "DEVICE_UUID",
  "group_id": "GROUP_ROOM_UUID",
  "read_through_message_id": "MESSAGE_UUID"
}
```

Response:

```json
{
  "success": true,
  "message": "Read receipts stored successfully.",
  "data": {
    "updated_count": 5,
    "receipt_ids": ["RECEIPT_UUID"]
  }
}
```

Marks all authorized non-self group messages up to `read_through_message_id` as delivered and read.

---

### 9.3 `GET /messages/{message_id}/receipts/`

Response:

```json
{
  "success": true,
  "message": "Message receipts retrieved successfully.",
  "data": {
    "message_id": "MESSAGE_UUID",
    "delivered_count": 2,
    "read_count": 1,
    "receipts": [
      {
        "id": "RECEIPT_UUID",
        "message_id": "MESSAGE_UUID",
        "recipient_user_id": "2",
        "recipient_device_id": "DEVICE_UUID",
        "delivered_at": "...",
        "read_at": null,
        "created_at": "...",
        "updated_at": "..."
      }
    ]
  }
}
```

---

## 10. Group management endpoint contracts

### 10.1 `GET /groups/`

Response:

```json
{
  "success": true,
  "message": "Groups retrieved successfully.",
  "data": [
    {
      "id": "GROUP_ROOM_UUID",
      "room_id": "GROUP_ROOM_UUID",
      "room_type": "group",
      "name": "Project Team",
      "description": "",
      "avatar_storage_key": "",
      "created_by_user_id": "1",
      "max_members": 100,
      "join_history_visible": false,
      "only_admins_can_send": false,
      "only_admins_can_edit_info": true,
      "is_active": true,
      "caller_role": "owner",
      "member_count": 3,
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

---

### 10.2 `POST /groups/`

Request:

```json
{
  "name": "Project Team",
  "description": "Team discussion",
  "member_user_ids": ["2", "3"],
  "max_members": 100,
  "join_history_visible": false,
  "only_admins_can_send": false,
  "only_admins_can_edit_info": true
}
```

Rules:

- creator becomes `owner`
- creator must not be included in `member_user_ids`
- default max members: 100
- max max-members: 500
- group creation creates initial encryption epoch `1`
- backend validates member IDs against Identity service

Response `201`:

```json
{
  "success": true,
  "message": "Group created successfully.",
  "data": {
    "id": "GROUP_ROOM_UUID",
    "room_id": "GROUP_ROOM_UUID",
    "room_type": "group",
    "name": "Project Team",
    "description": "Team discussion",
    "avatar_storage_key": "",
    "created_by_user_id": "1",
    "max_members": 100,
    "join_history_visible": false,
    "only_admins_can_send": false,
    "only_admins_can_edit_info": true,
    "is_active": true,
    "caller_role": "owner",
    "member_count": 3,
    "member_user_ids": ["1", "2", "3"],
    "members": [
      {
        "user_id": "1",
        "role": "owner",
        "is_active": true,
        "joined_at": "..."
      }
    ],
    "created_at": "...",
    "updated_at": "..."
  }
}
```

---

### 10.3 `GET /groups/{group_id}/`

Returns same detailed group shape as create.

---

### 10.4 `PATCH /groups/{group_id}/`

Request: one or more fields.

```json
{
  "name": "New Name",
  "description": "Updated description",
  "avatar_storage_key": "encrypted-avatar/storage-key",
  "max_members": 200,
  "join_history_visible": false,
  "only_admins_can_send": true,
  "only_admins_can_edit_info": true
}
```

Only owner/admin can edit group info when permitted.

---

### 10.5 Membership endpoints

Member shape:

```json
{
  "user_id": "2",
  "role": "member",
  "is_active": true,
  "joined_at": "...",
  "left_at": null,
  "removed_at": null,
  "banned_at": null,
  "added_by_user_id": "1",
  "removed_by_user_id": null,
  "membership_version": 1
}
```

Roles:

- `owner`
- `admin`
- `member`

#### `GET /groups/{group_id}/members/`

Response data is `GroupMember[]`.

#### `POST /groups/{group_id}/members/`

Request:

```json
{
  "member_user_ids": ["4", "5"]
}
```

Response `201`: added/reactivated `GroupMember[]`.

Adding/removing/leaving/banning members triggers security transition/epoch rotation hooks in the backend. The frontend must refresh epochs and sender-key distribution state after membership changes.

#### `DELETE /groups/{group_id}/members/{user_id}/`

Removes a member. Response data is a `GroupMember`.

#### `PATCH /groups/{group_id}/members/{user_id}/role/`

Request:

```json
{
  "role": "admin"
}
```

Valid target roles: `admin`, `member`.

#### `POST /groups/{group_id}/leave/`

Current user leaves group. Response data is a `GroupMember`.

#### `POST /groups/{group_id}/transfer-ownership/`

Request:

```json
{
  "new_owner_user_id": "2"
}
```

Response:

```json
{
  "success": true,
  "message": "Group ownership transferred successfully.",
  "data": {
    "old_owner": { "user_id": "1", "role": "admin" },
    "new_owner": { "user_id": "2", "role": "owner" }
  }
}
```

#### `POST /groups/{group_id}/members/{user_id}/ban/`

Bans member. Response data is a `GroupMember`.

#### `POST /groups/{group_id}/members/{user_id}/unban/`

Unbans member. Response data is a `GroupMember`.

---

## 11. Group E2EE endpoint contracts

### 11.1 `GET /groups/{group_id}/epochs/current/`

Response:

```json
{
  "success": true,
  "message": "Current group epoch retrieved successfully.",
  "data": {
    "id": "EPOCH_UUID",
    "group_room_id": "GROUP_ROOM_UUID",
    "epoch_number": 1,
    "status": "active",
    "rotation_reason": "initial",
    "created_by_user_id": "1",
    "membership_snapshot_hash": "HEX_SHA256",
    "created_at": "...",
    "closed_at": null
  }
}
```

Epoch status values:

- `active`
- `closed`

Rotation reasons include:

- `initial`
- `member_added`
- `member_removed`
- `member_left`
- `member_banned`
- `manual`
- `security_incident`

---

### 11.2 `GET /groups/{group_id}/epochs/`

Response data is `GroupEncryptionEpoch[]`.

---

### 11.3 `POST /groups/{group_id}/epochs/rotate/`

Request:

```json
{
  "reason": "manual"
}
```

Allowed request reasons:

- `manual`
- `security_incident`

Response data is new active epoch.

Frontend must revoke/stop using old local sender keys and create/register/distribute a fresh sender key for the new epoch.

---

### 11.4 `GET /groups/{group_id}/devices/?epoch_number=1`

Returns active member devices for a group epoch.

Response:

```json
{
  "success": true,
  "message": "Group device roster retrieved successfully.",
  "data": [
    {
      "user_id": "2",
      "membership_version": 1,
      "device_id": "DEVICE_UUID",
      "device_name": "Chrome",
      "platform": "web",
      "registration_id": 20001,
      "identity_key_public": "BASE64_IDENTITY_PUBLIC",
      "signed_prekey_id": 1,
      "signed_prekey_public": "BASE64_SIGNED_PREKEY_PUBLIC",
      "signed_prekey_signature": "BASE64_SIGNATURE",
      "key_algorithm": "curve25519",
      "key_bundle_version": 1,
      "epoch_number": 1,
      "membership_snapshot_hash": "HEX_SHA256"
    }
  ]
}
```

Use this to establish pairwise sessions and encrypt sender-key distributions.

---

### 11.5 `POST /groups/{group_id}/sender-keys/register/`

Registers public metadata for current device's local group sender key.

Request:

```json
{
  "sender_device_id": "DEVICE_UUID",
  "epoch_number": 1,
  "sender_key_id": "SENDER_KEY_PUBLIC_UUID",
  "signing_public_key": "BASE64_ED25519_PUBLIC_KEY",
  "key_algorithm": "group-sender-key-v1",
  "signing_algorithm": "ed25519",
  "key_version": 1
}
```

Response `201` or `200`:

```json
{
  "success": true,
  "message": "Group sender key registered successfully.",
  "data": {
    "id": "SERVER_SENDER_KEY_ROW_UUID",
    "group_room_id": "GROUP_ROOM_UUID",
    "epoch_id": "EPOCH_UUID",
    "epoch_number": 1,
    "sender_user_id": "1",
    "sender_device_id": "DEVICE_UUID",
    "sender_key_id": "SENDER_KEY_PUBLIC_UUID",
    "signing_public_key": "BASE64_ED25519_PUBLIC_KEY",
    "key_algorithm": "group-sender-key-v1",
    "signing_algorithm": "ed25519",
    "key_version": 1,
    "highest_accepted_iteration": 0,
    "is_active": true,
    "created_at": "...",
    "revoked_at": null
  }
}
```

Never send chain key or private signing key.

---

### 11.6 `GET /groups/{group_id}/sender-keys/mine/?device_id={device_id}`

Returns current user's active sender key for this device and group, or `null`.

Response:

```json
{
  "success": true,
  "message": "Group sender key lookup completed.",
  "data": null
}
```

or a `GroupSenderKey` object.

---

### 11.7 `DELETE /groups/{group_id}/sender-keys/{sender_key_id}/`

Revokes sender key. Response data is `GroupSenderKey` with `is_active: false` and `revoked_at` set.

---

### 11.8 `POST /groups/{group_id}/sender-keys/{sender_key_id}/distributions/`

Stores encrypted sender-key copies for recipient devices.

Request:

```json
{
  "epoch_number": 1,
  "distributions": [
    {
      "recipient_user_id": "2",
      "recipient_device_id": "DEVICE_UUID",
      "encrypted_sender_key": "BASE64_PAIRWISE_ENCRYPTED_GROUP_SENDER_KEY_BUNDLE",
      "distribution_metadata": {
        "algorithm": "double-ratchet-v1",
        "nonce": "BASE64_24_BYTE_NONCE",
        "content_format": "myna-group-sender-key-distribution-v1"
      },
      "distribution_version": 1
    }
  ]
}
```

Response:

```json
{
  "success": true,
  "message": "Group sender-key distributions stored.",
  "data": {
    "created_count": 2,
    "existing_count": 0,
    "missing_required_device_ids": [],
    "is_send_ready": true,
    "distributions": [
      {
        "id": "DISTRIBUTION_UUID",
        "sender_key_id": "SERVER_SENDER_KEY_ROW_UUID",
        "sender_key_public_id": "SENDER_KEY_PUBLIC_UUID",
        "group_room_id": "GROUP_ROOM_UUID",
        "epoch_number": 1,
        "sender_user_id": "1",
        "sender_device_id": "DEVICE_UUID",
        "recipient_user_id": "2",
        "recipient_device_id": "DEVICE_UUID",
        "encrypted_sender_key": "BASE64_CIPHERTEXT",
        "distribution_metadata": {},
        "distribution_version": 1,
        "status": "stored",
        "created_at": "...",
        "acknowledged_at": null
      }
    ]
  }
}
```

The request rejects field names or metadata names containing secret fragments like `private`, `secret`, `sender_chain`, `message_key`, `ratchet`, `recovery_key`, `plaintext`.

---

### 11.9 `GET /groups/{group_id}/sender-keys/{sender_key_id}/pending/`

Response:

```json
{
  "success": true,
  "message": "Group sender-key distribution coverage retrieved.",
  "data": {
    "sender_key_id": "SENDER_KEY_PUBLIC_UUID",
    "epoch_number": 1,
    "required_device_count": 5,
    "covered_device_count": 4,
    "pending_device_count": 1,
    "is_send_ready": false,
    "pending_devices": [
      {
        "user_id": "3",
        "device_id": "DEVICE_UUID",
        "identity_key_public": "..."
      }
    ]
  }
}
```

Use before enabling send in a group for a new sender key.

---

### 11.10 `GET /groups/{group_id}/sender-key-distributions/inbox/?device_id={device_id}`

Recipient device fetches encrypted sender-key distributions addressed to it.

Response data is `GroupSenderKeyDistribution[]`.

Frontend flow:

1. Fetch inbox for current device.
2. Decrypt each `encrypted_sender_key` using pairwise session/device-sync crypto.
3. Store decrypted group sender key locally in IndexedDB.
4. Acknowledge successful imports.

---

### 11.11 `POST /groups/{group_id}/sender-key-distributions/acknowledge/`

Request:

```json
{
  "device_id": "DEVICE_UUID",
  "distribution_ids": ["DISTRIBUTION_UUID"]
}
```

Response data is acknowledged `GroupSenderKeyDistribution[]` with `status: "acknowledged"`.

---

### 11.12 `GET /groups/{group_id}/recovery-recipients/`

Returns active group members with active recovery public keys for the current epoch.

Response:

```json
{
  "success": true,
  "message": "Group recovery recipients retrieved successfully.",
  "data": {
    "group_id": "GROUP_ROOM_UUID",
    "epoch_number": 1,
    "recipients": [
      {
        "user_id": "1",
        "recovery_public_key": "BASE64_RECOVERY_PUBLIC_KEY",
        "recovery_version": 1
      }
    ]
  }
}
```

Use these recipients to create `recovery_envelopes` for group messages.

---

### 11.13 `POST /messages/group/`

Sends encrypted group message.

Request:

```json
{
  "group_id": "GROUP_ROOM_UUID",
  "sender_device_id": "DEVICE_UUID",
  "client_message_id": "CLIENT_MESSAGE_UUID",
  "epoch_number": 1,
  "sender_key_id": "SENDER_KEY_PUBLIC_UUID",
  "chain_iteration": 1,
  "message_type": "text",
  "encrypted_payload": "BASE64_GROUP_CIPHERTEXT",
  "encryption_metadata": {
    "algorithm": "group-sender-key-v1",
    "nonce": "BASE64_24_BYTE_NONCE",
    "content_format": "myna-group-message-json-v1"
  },
  "signature": "BASE64_ED25519_SIGNATURE_OVER_CANONICAL_MESSAGE_EVENT",
  "reply_to_message_id": null,
  "client_sent_at": "2026-06-27T19:30:00Z",
  "recovery_envelopes": [
    {
      "recovery_owner_user_id": "1",
      "recovery_key_version": 1,
      "wrapped_message_key": "BASE64_RECOVERY_WRAPPED_GROUP_MESSAGE_KEY",
      "key_wrap_metadata": {
        "algorithm": "recovery-box-v1",
        "nonce": "BASE64_24_BYTE_NONCE"
      },
      "envelope_version": 1
    }
  ]
}
```

Required:

- `encryption_metadata.algorithm` must be `group-sender-key-v1`.
- `chain_iteration` must be greater than sender key's current `highest_accepted_iteration`.
- Sender key must be active for the current epoch and current device.
- Sender-key distributions must cover all required active devices except sender device.
- If active recovery recipients exist, `recovery_envelopes` must cover all of them.

Response `201` or `200` idempotent:

```json
{
  "success": true,
  "message": "Group message sent successfully.",
  "data": {
    "message_created": true,
    "message": {
      "id": "GROUP_MESSAGE_ENCRYPTION_ROW_UUID",
      "message_id": "MESSAGE_UUID",
      "room_id": "GROUP_ROOM_UUID",
      "sender_user_id": "1",
      "sender_device_id": "DEVICE_UUID",
      "client_message_id": "CLIENT_MESSAGE_UUID",
      "message_type": "text",
      "encrypted_payload": "BASE64_GROUP_CIPHERTEXT",
      "encryption_metadata": {
        "algorithm": "group-sender-key-v1"
      },
      "epoch_number": 1,
      "sender_key_id": "SENDER_KEY_PUBLIC_UUID",
      "chain_iteration": 1,
      "signature": "BASE64_SIGNATURE",
      "reply_to_id": null,
      "client_sent_at": "...",
      "created_at": "..."
    }
  }
}
```

Encrypted edit/delete/reaction events:

For `message_type` of `edit`, `delete`, or `reaction`, `encryption_metadata` must include:

```json
{
  "algorithm": "group-sender-key-v1",
  "event_type": "edit",
  "target_message_id": "MESSAGE_UUID"
}
```

For `edit` and `delete`, backend requires the original sender to create the event.

---

### 11.14 `GET /messages/groups/{group_id}/history/?device_id={device_id}&page_size=50&cursor=...`

Response:

```json
{
  "success": true,
  "message": "Group encrypted history retrieved successfully.",
  "data": {
    "items": [
      {
        "id": "MESSAGE_UUID",
        "room_id": "GROUP_ROOM_UUID",
        "sender_user_id": "1",
        "sender_device_id": "DEVICE_UUID",
        "client_message_id": "CLIENT_MESSAGE_UUID",
        "message_type": "text",
        "encrypted_payload": "BASE64_GROUP_CIPHERTEXT",
        "encryption_metadata": {
          "algorithm": "group-sender-key-v1"
        },
        "epoch_number": 1,
        "sender_key_id": "SENDER_KEY_PUBLIC_UUID",
        "chain_iteration": 1,
        "signature": "BASE64_SIGNATURE",
        "signing_public_key": "BASE64_ED25519_PUBLIC_KEY",
        "reply_to_id": null,
        "client_sent_at": "...",
        "created_at": "..."
      }
    ],
    "next_cursor": null,
    "page_size": 50
  }
}
```

Frontend decrypt flow:

1. Ensure current device has sender-key distributions imported for relevant `sender_key_id` and `epoch_number`.
2. Verify Ed25519 `signature` using `signing_public_key`.
3. Derive group message key for `chain_iteration`.
4. Decrypt `encrypted_payload` using metadata nonce.
5. Store decrypted results locally only.

---

## 12. Recommended frontend flows

### 12.1 First login on a browser/device

1. Identity login returns access token.
2. Check IndexedDB for existing local device secret state.
3. If absent, generate device keys and one-time prekeys.
4. Call `POST /e2ee/devices/register/`.
5. Store only private keys locally.
6. Call `GET /e2ee/recovery/status/`.
7. If recovery exists and user wants old history, unlock/download recovery.
8. Otherwise enter room list.

---

### 12.2 Direct send flow

1. User selects contact from Identity/Contacts service.
2. Call `POST /e2ee/prekey-bundles/claim/` for recipient.
3. Establish/update pairwise sessions for recipient devices.
4. Resolve recovery public keys using `/e2ee/recovery/public-keys/resolve/` for `[senderUserId, recipientUserId]`.
5. Build plaintext message JSON.
6. Generate message content key and encrypt plaintext.
7. Wrap content key for all required device envelopes.
8. Wrap content key for all active recovery owners.
9. Call `POST /messages/direct/`.
10. Optimistically show pending message; reconcile by `client_message_id`.
11. Poll or refresh history until Phase 13 WebSockets are ready.

---

### 12.3 Direct receive flow

1. Poll `GET /rooms/` and room history.
2. For each encrypted history item, locate `device_envelope`.
3. Unwrap content key by `protocol`.
4. Decrypt payload.
5. Store decrypted local render model in IndexedDB cache.
6. Send delivered receipt after successful storage/decryption where appropriate.

---

### 12.4 Recovery setup flow

1. Generate recovery X25519 keypair.
2. Generate recovery secret/passkey PRF material.
3. Encrypt recovery private key with `xchacha20poly1305-ietf`.
4. Upload public key and encrypted private key through `/e2ee/recovery/setup/`.
5. Show user recovery key and warning.
6. Run coverage check.
7. Backfill if needed.

---

### 12.5 New device history recovery flow

1. Register device.
2. Download recovery bundle.
3. User provides recovery key or passkey PRF.
4. Decrypt recovery private key locally.
5. Fetch `/messages/recovery-history/` pages.
6. Decrypt recovery envelopes and message payloads.
7. Batch rewrap keys for the new device using `/messages/recovery/rewrap/`.
8. After rewrap, normal `/rooms/{room_id}/history/?device_id=...` works for recovered messages.

---

### 12.6 Group creation flow

1. Create group via `/groups/`.
2. Fetch current epoch.
3. Fetch group device roster.
4. Generate local group sender key and Ed25519 signing key for current device/epoch.
5. Register sender key public metadata.
6. Encrypt/distribute sender key to all required recipient devices.
7. Check pending coverage.
8. Enable message composer only when `is_send_ready` is true.

---

### 12.7 Group receive flow

1. Fetch sender-key distribution inbox for current device.
2. Decrypt and store sender keys locally.
3. Acknowledge imported distributions.
4. Fetch group history.
5. Verify signatures.
6. Derive per-message keys by sender key and chain iteration.
7. Decrypt payloads.
8. Mark delivered/read as needed.

---

## 13. Phase 13 WebSocket placeholder

Do not implement WebSocket transport now.

Frontend may prepare an interface like:

```ts
type MessageTransport = {
  sendDirectMessage(payload: SendDirectMessageRequest): Promise<SendDirectMessageResponse>;
  sendGroupMessage(payload: SendGroupMessageRequest): Promise<SendGroupMessageResponse>;
  subscribe?(): void;
};
```

Current implementation must call REST. Later Phase 13 WebSockets should only push encrypted events and should reuse the exact same encrypted payload/envelope contracts. WebSockets must not introduce plaintext paths.

---

## 14. Phase 14 placeholder

Phase 14 is not implemented in the uploaded backend. Do not build a required frontend dependency on it. Leave clean TODO boundaries and keep the current UI functional with REST APIs.

---

## 15. Known frontend limitations from current backend

These are important for the coding agent:

1. There is no general authenticated own-device list/rename/revoke API in this backend zip.
2. Direct send validation requires envelopes for all active sender and recipient devices, but recipient devices are discoverable through prekey claim while sender device discovery is not fully exposed.
3. Attachment download metadata currently checks uploader ownership. Recipients should get storage references from decrypted message plaintext unless backend later adds recipient attachment access.
4. WebSocket delivery, typing, presence, and push are not implemented.
5. Identity, profile, contacts, blocking, and account lifecycle are separate service responsibilities.
6. The backend does not cryptographically verify ciphertext correctness; frontend tests must enforce strict encryption rules.

---

## 16. TypeScript DTO starter types

```ts
export type UUID = string;
export type ISODateTime = string;

export type DevicePlatform = "android" | "ios" | "web" | "desktop" | "other";
export type MessageType =
  | "text"
  | "image"
  | "video"
  | "audio"
  | "file"
  | "location"
  | "contact"
  | "edit"
  | "delete"
  | "reaction"
  | "system";

export type MessageEnvelopeProtocol = "double_ratchet" | "group_sender_key" | "device_sync";

export type MessageKeyEnvelopeInput = {
  recipient_device_id: UUID;
  protocol: MessageEnvelopeProtocol;
  session_reference?: string;
  wrapped_message_key: string;
  key_wrap_metadata?: Record<string, unknown>;
  envelope_version?: number;
};

export type RecoveryEnvelopeInput = {
  recovery_owner_user_id: string;
  recovery_key_version: number;
  wrapped_message_key: string;
  key_wrap_metadata: {
    algorithm: "recovery-box-v1";
    nonce: string;
    [key: string]: unknown;
  };
  envelope_version?: number;
};

export type SendDirectMessageRequest = {
  recipient_user_id: string;
  sender_device_id: UUID;
  client_message_id: UUID;
  message_type: MessageType;
  encrypted_payload: string;
  encryption_metadata: Record<string, unknown>;
  encryption_version?: number;
  reply_to_id?: UUID | null;
  client_sent_at?: ISODateTime | null;
  envelopes: MessageKeyEnvelopeInput[];
  recovery_envelopes?: RecoveryEnvelopeInput[];
};

export type SendGroupMessageRequest = {
  group_id: UUID;
  sender_device_id: UUID;
  client_message_id: UUID;
  epoch_number: number;
  sender_key_id: UUID;
  chain_iteration: number;
  message_type: MessageType;
  encrypted_payload: string;
  encryption_metadata: {
    algorithm: "group-sender-key-v1";
    [key: string]: unknown;
  };
  signature: string;
  reply_to_message_id?: UUID | null;
  client_sent_at?: ISODateTime | null;
  recovery_envelopes?: RecoveryEnvelopeInput[];
};
```

---

## 17. Testing checklist for frontend agent

The generated frontend must pass these behavior checks:

- [ ] It refuses to send message plaintext to the API.
- [ ] It registers a device before sending or reading messages.
- [ ] It uploads one-time prekeys.
- [ ] It can claim recipient prekey bundles.
- [ ] It creates direct message device envelopes with correct protocols.
- [ ] It creates recovery envelopes only for users with active recovery.
- [ ] It handles `409` idempotency correctly.
- [ ] It decrypts direct history only in the crypto worker.
- [ ] It can configure, unlock, and use recovery.
- [ ] It can backfill recovery envelopes.
- [ ] It encrypts attachments before upload.
- [ ] It never stores attachment keys in backend-visible metadata.
- [ ] It creates groups and fetches current epoch.
- [ ] It registers and distributes group sender keys before group send.
- [ ] It refuses group send until sender-key distribution coverage is complete.
- [ ] It verifies group signatures before rendering decrypted group messages.
- [ ] It sends delivered/read receipts only after authorization/decryption logic is complete.
- [ ] It does not use WebSockets yet.

---

## 18. Final implementation instruction for the AI coding agent

Build the frontend as a strict E2EE Messenger client. Start with the REST API client, device registration, crypto worker, IndexedDB storage, and direct-message send/read. Then add recovery setup/history/rewrap/backfill. Then add encrypted attachments. Then add groups, sender-key distribution, group send/history, and receipts. Leave Phase 13 WebSockets and Phase 14 as TODO interfaces only.

The backend is a ciphertext router and encrypted storage service. The frontend owns all encryption, decryption, key generation, key wrapping, recovery unlock, sender-key handling, and plaintext rendering.
