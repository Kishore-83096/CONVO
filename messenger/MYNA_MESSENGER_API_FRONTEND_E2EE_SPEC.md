# Myna Messenger Service
## Complete REST API, React Frontend, Cloud Recovery, and Future WebSocket Integration Contract

**Document version:** 2.0  
**Updated:** 27 June 2026  
**Backend:** Django 5.2 + Django REST Framework  
**Frontend target:** React + TypeScript + Vite  
**Current message transport:** REST APIs  
**Near-future real-time transport:** Django Channels + Redis + WebSocket  
**Security goal:** Strict end-to-end encryption. The server stores ciphertext, public keys, encrypted private-key bundles, and wrapped message keys only.  
**Verified backend regression baseline:** **94 tests passing**

> **Codex instruction:** Treat this document as the frontend implementation contract. Do not invent request fields, do not send plaintext or private keys, and do not replace the recovery/device state machines with UI-only shortcuts.

---

# 1. Purpose

This document is written so a coding agent can build the Myna messenger frontend without needing to reverse-engineer the cryptographic workflow from individual Django files.

It defines:

- Every currently implemented messenger REST endpoint.
- Exact recovery request and response shapes.
- Status codes and idempotency rules.
- Which operations happen on the client versus the server.
- Required React screens, hooks, stores, workers, and state machines.
- The direct-message send and receive flow.
- Cloud history recovery on a new device.
- Recovery backfill, coverage, rotation, and deletion.
- The future WebSocket transport planned for instant message delivery.

Authentication, profile management, contact search, contact saving, blocking, and account lifecycle remain owned by the separate Identity service. The Messenger service trusts the external user ID in the verified access-token `sub` claim.

---

# 2. Status and source-of-truth rules

| Label | Meaning |
|---|---|
| **IMPLEMENTED + TESTED** | Implemented and covered by the current automated suite. |
| **IMPLEMENTED** | Implemented, but the exact adapter should still be checked against its serializer. |
| **DIAGNOSTIC** | Development helper; do not make the production UI depend on it. |
| **PLANNED** | Not implemented. Do not call it from the current frontend. |

Current verification:

```text
94 backend tests passed
```

The backend code remains the final source of truth when this document explicitly says **serializer confirmation required**. Everywhere else, use the contracts below exactly.

---

# 3. Current implemented scope

## Implemented and tested now

- Shared JWT authentication with the Identity service.
- Device public-key registration.
- One-time-prekey upload.
- Atomic recipient prekey-bundle claim.
- Direct-room creation/reuse.
- Authenticated room listing.
- Atomic encrypted direct-message storage.
- Per-active-device normal message-key envelopes.
- Optional-but-conditionally-mandatory recovery envelopes on direct messages.
- Sender plus `client_message_id` idempotency.
- Device-specific encrypted room history.
- Encrypted recovery setup, status, and bundle download.
- Active recovery public-key resolution.
- User-specific encrypted recovery history.
- Rewrapping recovered message keys for a new device.
- Recovery-aware sending for new messages.
- Atomic recovery key rotation.
- Permanent recovery deletion.
- Backfilling old messages created before recovery was enabled.
- Recovery coverage and stale-version auditing.
- Atomic rollback and retry-conflict protection across recovery operations.

## Not implemented yet

- WebSocket connections and instant push delivery.
- Delivery receipts.
- Read receipts.
- Typing indicators.
- Presence.
- Message editing or deletion.
- Attachment APIs.
- Group E2EE and sender-key epochs.
- Authenticated device-list/rename/revoke APIs for UI management.
- A dedicated direct-room resolve endpoint.
- Messenger-to-Identity recipient/block validation inside the send transaction.
- JWT revocation synchronization.

## Near-future WebSocket statement

Myna will add WebSockets using Django Channels and Redis for instant delivery. WebSockets will be a transport layer over the same encrypted message contract. They must not introduce a second plaintext or weaker storage path. REST will remain the source of truth for history, recovery, reconciliation, and safe retries.

---

# 4. Architecture and trust boundaries

```text
React UI
   |
   | commands and render models only
   v
Messenger application services
   |
   +--> typed REST adapters
   +--> recovery coordinator
   +--> encrypted outbox
   +--> IndexedDB repositories
   |
   v
Dedicated crypto Web Worker
   |
   +--> device private keys
   +--> pairwise ratchet state
   +--> device-sync state
   +--> recovery private key while unlocked
   +--> plaintext only during local encrypt/decrypt

Network / Messenger backend
   |
   +--> ciphertext
   +--> public key bundles
   +--> encrypted recovery private-key bundle
   +--> wrapped content keys
   +--> routing metadata
```

The server must never receive:

- Message plaintext.
- Plaintext message content keys.
- Device identity private keys.
- Signed-prekey private keys.
- One-time-prekey private keys.
- Double Ratchet root keys or chain keys.
- Plaintext recovery private key.
- Independent recovery key or passphrase.
- WebAuthn PRF output.

The server may store:

- Device public identity/prekey material.
- Message ciphertext.
- Normal per-device wrapped content keys.
- Recovery public key.
- Client-encrypted recovery private-key bundle.
- Per-user recovery-wrapped content keys.
- Versioned cryptographic metadata.

---

# 5. Environment configuration

```env
VITE_IDENTITY_API_BASE_URL=https://identity.example.com/api/v1
VITE_MESSENGER_API_BASE_URL=https://messenger.example.com/api/v1
VITE_MESSENGER_WS_BASE_URL=wss://messenger.example.com
```

Local example:

```env
VITE_IDENTITY_API_BASE_URL=http://localhost:5000/api/v1
VITE_MESSENGER_API_BASE_URL=http://localhost:8000/api/v1
VITE_MESSENGER_WS_BASE_URL=ws://localhost:8000
```

Normalize trailing slashes once in `src/config/env.ts`.

Do not use the WebSocket base URL until the backend realtime phase is implemented.

---

# 6. Authentication

Every protected request uses the Identity-service access token:

```http
Authorization: Bearer <access-token>
Content-Type: application/json
```

The Messenger service verifies signature, expiry, `nbf`, token type, and `sub`. The owner user ID is always derived from the authenticated principal. The frontend must never send an owner field to override the JWT identity.

Typical unauthenticated response:

```text
401 Unauthorized
```

```json
{
  "detail": "Authentication credentials were not provided."
}
```

Create one shared API client. On `401`, clear the Identity-service session and local unlocked secrets. Do not delete encrypted IndexedDB data automatically unless the user explicitly removes the device.

---

# 7. Common response contracts

```ts
export interface ApiSuccess<T> {
  success: true;
  message: string;
  data: T;
}

export interface ApiFailure {
  success: false;
  message: string;
  errors?: Record<string, string[]>;
}
```

Validation errors normally use:

```json
{
  "success": false,
  "message": "Validation failed.",
  "errors": {
    "field_name": ["Error message."]
  }
}
```

Frontend error classes should preserve:

- HTTP status.
- Backend `message`.
- Field errors.
- Whether retrying the exact same encrypted request is safe.

Never log request bodies containing wrapped keys or encrypted private-key bundles.

---

# 8. Complete API index

| Status | Method | Path | Purpose |
|---|---|---|---|
| DIAGNOSTIC | `GET` | `/api/v1/auth/whoami/` | Verify JWT integration. |
| IMPLEMENTED | `POST` | `/api/v1/e2ee/devices/register/` | Register public device bundle. |
| IMPLEMENTED | `POST` | `/api/v1/e2ee/devices/{device_id}/prekeys/` | Upload one-time public prekeys. |
| IMPLEMENTED | `POST` | `/api/v1/e2ee/prekey-bundles/claim/` | Claim recipient device public bundles. |
| IMPLEMENTED + TESTED | `POST` | `/api/v1/e2ee/recovery/setup/` | Create encrypted cloud recovery. |
| IMPLEMENTED + TESTED | `GET` | `/api/v1/e2ee/recovery/status/` | Read recovery configuration state. |
| IMPLEMENTED + TESTED | `GET` | `/api/v1/e2ee/recovery/bundle/` | Download owner’s encrypted recovery bundle. |
| IMPLEMENTED + TESTED | `POST` | `/api/v1/e2ee/recovery/public-keys/resolve/` | Resolve active recovery public keys. |
| IMPLEMENTED + TESTED | `POST` | `/api/v1/e2ee/recovery/rotate/` | Atomically rotate bundle and all recovery envelopes. |
| IMPLEMENTED + TESTED | `DELETE` | `/api/v1/e2ee/recovery/` | Permanently delete the user’s recovery data. |
| IMPLEMENTED + TESTED | `GET` | `/api/v1/messages/rooms/` | List active rooms for the authenticated user. |
| IMPLEMENTED + TESTED | `POST` | `/api/v1/messages/direct/` | Store an encrypted direct message. |
| IMPLEMENTED + TESTED | `GET` | `/api/v1/messages/rooms/{room_id}/history/` | Device-filtered encrypted room history. |
| IMPLEMENTED + TESTED | `GET` | `/api/v1/messages/recovery-history/` | User recovery history with recovery envelopes. |
| IMPLEMENTED + TESTED | `POST` | `/api/v1/messages/recovery/rewrap/` | Rewrap recovered keys for a new device. |
| IMPLEMENTED + TESTED | `GET` | `/api/v1/messages/recovery/backfill/candidates/` | Find old messages missing recovery. |
| IMPLEMENTED + TESTED | `POST` | `/api/v1/messages/recovery/backfill/` | Add recovery envelopes to old messages. |
| IMPLEMENTED + TESTED | `GET` | `/api/v1/messages/recovery/coverage/` | Audit recovery completeness and stale versions. |

---

# 9. Shared TypeScript types

```ts
export type UUID = string;
export type ExternalUserId = string;
export type Base64String = string;
export type ISODateTime = string;

export type DevicePlatform =
  | "web"
  | "android"
  | "ios"
  | "desktop"
  | string;

export type MessageType =
  | "text"
  | "image"
  | "video"
  | "audio"
  | "file"
  | "location"
  | "contact"
  | "system";

export type EnvelopeProtocol =
  | "double_ratchet"
  | "device_sync"
  | "group_sender_key";

export type RecoveryUnlockMethod =
  | "recovery_key"
  | "webauthn_prf"
  | "recovery_key_and_webauthn_prf";

export interface RecoveryBundleEncryptionMetadata {
  algorithm: "xchacha20poly1305-ietf";
  nonce: Base64String;
  unlock_method: RecoveryUnlockMethod;
  [key: string]: unknown;
}

export interface RecoveryKeyWrapMetadata {
  algorithm: "recovery-box-v1";
  nonce: Base64String;
  [key: string]: unknown;
}

export interface DeviceSyncWrapMetadata {
  algorithm: "device-sync-v1";
  nonce: Base64String;
  [key: string]: unknown;
}
```

Public device record and local private state:

```ts
export interface DevicePublicRecord {
  id: UUID;
  user_id: ExternalUserId;
  device_name: string;
  platform: DevicePlatform;
  registration_id: number;
  identity_key_public: Base64String;
  signed_prekey_id: number;
  signed_prekey_public: Base64String;
  signed_prekey_signature: Base64String;
  key_algorithm: string;
  key_bundle_version: number;
  is_active: boolean;
  created_at?: ISODateTime;
  updated_at?: ISODateTime;
  last_seen_at?: ISODateTime | null;
}

export interface LocalPrivateDeviceState {
  deviceId: UUID;
  identityAgreementPrivateKey: Uint8Array;
  identitySigningPrivateKey: Uint8Array;
  signedPreKeyPrivateKey: Uint8Array;
  oneTimePreKeyPrivateKeys: Map<number, Uint8Array>;
  sessions: Map<string, EncryptedRatchetState>;
}
```

Never keep `LocalPrivateDeviceState` in React component state or persisted Redux state.

---

# 10. Diagnostic JWT endpoint

## `GET /api/v1/auth/whoami/`

**Status:** DIAGNOSTIC

Purpose:

- Verify the Identity-service JWT can be accepted by the messenger service.
- Useful during local integration.
- Do not make this a required production startup dependency.

Request:

```http
GET /api/v1/auth/whoami/
Authorization: Bearer <access-token>
```

Expected data concept:

```json
{
  "user_id": "123"
}
```

The exact diagnostic response may differ. The frontend should not rely on it after authentication integration is stable.

---

# 11. Register an E2EE device

## `POST /api/v1/e2ee/devices/register/`

**Status:** IMPLEMENTED  
**Authentication:** Required

The React client generates all private and public cryptographic material locally. It sends only the public bundle.

## Request

```ts
export interface RegisterDeviceRequest {
  device_name: string;
  platform: DevicePlatform;
  registration_id: number;

  identity_key_public: Base64String;
  signed_prekey_id: number;
  signed_prekey_public: Base64String;
  signed_prekey_signature: Base64String;

  key_algorithm: string;
  key_bundle_version: number;
}
```

Example:

```json
{
  "device_name": "Chrome on Windows",
  "platform": "web",
  "registration_id": 184728391,
  "identity_key_public": "<base64-public-key>",
  "signed_prekey_id": 1,
  "signed_prekey_public": "<base64-public-key>",
  "signed_prekey_signature": "<base64-signature>",
  "key_algorithm": "curve25519",
  "key_bundle_version": 1
}
```

## Ownership

The server derives `user_id` from the JWT. The client must never send or override the owner ID.

## Response

Minimum frontend requirement:

```ts
export type RegisterDeviceResponse =
  ApiSuccess<DevicePublicRecord | { device: DevicePublicRecord }>;
```

**BACKEND CONFIRMATION:** Before freezing this exact response type, inspect the current serializer response and normalize it in the API adapter.

Recommended adapter:

```ts
function normalizeRegisteredDevice(
  data: DevicePublicRecord | { device: DevicePublicRecord },
): DevicePublicRecord {
  return "device" in data ? data.device : data;
}
```

## Frontend behavior

1. Generate device keys in the crypto worker.
2. Encrypt private device state into IndexedDB.
3. Call this endpoint with public values.
4. Store the returned server `device.id` in encrypted local state.
5. Upload one-time prekeys.
6. Never regenerate the identity key on every page refresh.

## Important production gap

`key_algorithm: "curve25519"` is not precise enough for a production protocol.

The final wire contract should explicitly identify:

- Identity agreement algorithm: for example `X25519`.
- Identity signature algorithm: for example `Ed25519` or a Signal-compatible XEdDSA construction.
- Signed-prekey agreement algorithm.
- KDF.
- AEAD.
- Protocol version.

A strict client should reject unknown algorithm versions rather than guessing.

---

# 12. Upload one-time prekeys

## `POST /api/v1/e2ee/devices/{device_id}/prekeys/`

**Status:** IMPLEMENTED  
**Authentication:** Required

Only the owner of the device may upload its prekeys.

## Request

```ts
export interface OneTimePreKeyUploadItem {
  key_id: number;
  public_key: Base64String;
}

export interface UploadOneTimePreKeysRequest {
  prekeys: OneTimePreKeyUploadItem[];
}
```

Example:

```json
{
  "prekeys": [
    {
      "key_id": 1001,
      "public_key": "<base64-public-key>"
    },
    {
      "key_id": 1002,
      "public_key": "<base64-public-key>"
    }
  ]
}
```

## Response

The frontend only needs to require:

```ts
export interface UploadPreKeysResult {
  uploaded_count?: number;
  available_count?: number;
  device_id?: UUID;
}

export type UploadPreKeysResponse =
  ApiSuccess<UploadPreKeysResult>;
```

**BACKEND CONFIRMATION:** Confirm exact response keys before final generated types.

## Frontend behavior

- Generate private/public one-time-prekey pairs locally.
- Upload only public keys.
- Store private one-time-prekeys encrypted in IndexedDB.
- Delete a private one-time-prekey after it is consumed to establish a session.
- Replenish before the available count reaches zero.
- Never reuse a one-time prekey.

Suggested thresholds:

```ts
const PREKEY_TARGET = 100;
const PREKEY_REPLENISH_THRESHOLD = 20;
```

These values are product configuration, not protocol constants.

---

# 12A. Claim recipient prekey bundles

## `POST /api/v1/e2ee/prekey-bundles/claim/`

**Status:** IMPLEMENTED  
**Authentication:** Required  
**Atomic behavior:** One-time-prekey consumption is performed transactionally.

Purpose:

- Obtain the recipient's public identity and signed-prekey bundle.
- Atomically claim an available one-time prekey when one exists.
- Create or refresh pairwise sessions for every active recipient device.

## Request

Use the target Identity-service user ID.

```ts
export interface ClaimPreKeyBundlesRequest {
  recipient_user_id: ExternalUserId;
}
```

Example:

```json
{
  "recipient_user_id": "42"
}
```

**BACKEND CONFIRMATION:** If the current serializer calls this field `user_id`, map the frontend name `recipient_user_id` to `user_id` in this single API adapter. Do not spread naming differences across the application.

## Normalized frontend response

```ts
export interface ClaimedOneTimePreKey {
  key_id: number;
  public_key: Base64String;
}

export interface ClaimedDevicePreKeyBundle {
  device_id: UUID;
  user_id: ExternalUserId;
  registration_id: number;

  identity_key_public: Base64String;
  signed_prekey_id: number;
  signed_prekey_public: Base64String;
  signed_prekey_signature: Base64String;

  key_algorithm: string;
  key_bundle_version: number;

  one_time_prekey: ClaimedOneTimePreKey | null;
}

export interface ClaimPreKeyBundlesResult {
  bundles: ClaimedDevicePreKeyBundle[];
}

export type ClaimPreKeyBundlesResponse =
  ApiSuccess<ClaimPreKeyBundlesResult>;
```

## Frontend security checks

Before creating a session:

1. Verify the signed-prekey signature.
2. Validate algorithm and version allowlists.
3. Validate public-key lengths and encoding.
4. Compare the recipient identity key with the previously trusted identity key.
5. If the identity key changed, stop automatic sending and display a security warning.
6. Consume the claimed one-time prekey only through the session-establishment flow.
7. Never trust `device_name` or other display metadata as cryptographic identity.

## Session creation

For a recipient device with no existing valid session:

1. Use X3DH/PQXDH-compatible session establishment.
2. Initialize a Double Ratchet session.
3. Store the resulting ratchet state encrypted in IndexedDB.
4. Build the first `double_ratchet` key envelope.
5. Do not send the recipient's private information to the server.

---


# 13. List rooms

## `GET /api/v1/messages/rooms/`

**Status:** IMPLEMENTED + TESTED  
**Authentication:** Required

Response shell:

```json
{
  "success": true,
  "message": "Rooms retrieved successfully.",
  "data": []
}
```

`data` is the output of the backend `RoomListItemSerializer` for active rooms where the authenticated user is an active member.

> **Serializer confirmation required:** Codex must read the current `apps/chat_messages/serializers.py::RoomListItemSerializer` before freezing the exact `RoomListItem` TypeScript interface. Do not fabricate plaintext previews or participant profile data that the serializer does not return.

Frontend behavior:

- Fetch after device bootstrap and authentication.
- Use room IDs returned by the Messenger service.
- Join Identity-service contact/profile data by external user ID in a separate view-model layer.
- Never treat a locally cached room list as the authorization source.
- Refresh after successful first send because the backend may have created the direct room.
- In the future, a WebSocket `room.updated` event will trigger a REST refresh or cache update.

---

# 14. Send an encrypted direct message

## `POST /api/v1/messages/direct/`

**Status:** IMPLEMENTED + TESTED  
**Authentication:** Required  
**Atomic:** Yes  
**Idempotency key:** authenticated sender + `client_message_id`

The request contains one encrypted payload, normal per-device envelopes, and recovery envelopes when either participant has active recovery.

## Normal device envelope

```ts
export interface MessageKeyEnvelopeInput {
  recipient_device_id: UUID;
  protocol: EnvelopeProtocol;
  session_reference: string;
  wrapped_message_key: Base64String;
  key_wrap_metadata: Record<string, unknown>;
  envelope_version: number;
}
```

Rules:

- Exactly one normal envelope is required for every active sender device and active recipient device.
- Sender devices use `device_sync`.
- Recipient devices use `double_ratchet`.
- Duplicate device IDs are rejected.
- Device ownership is resolved by the server.
- Any validation failure rolls back the room, message, normal envelopes, and recovery envelopes.

## Recovery envelope

```ts
export interface RecoveryEnvelopeInput {
  recovery_owner_user_id: ExternalUserId;
  recovery_key_version: number;
  wrapped_message_key: Base64String;
  key_wrap_metadata: RecoveryKeyWrapMetadata;
  envelope_version: number;
}
```

Recovery rules:

| Active recovery state | Required `recovery_envelopes` |
|---|---|
| Neither participant | Empty or omitted. |
| Sender only | One envelope owned by sender. |
| Recipient only | One envelope owned by recipient. |
| Both participants | Exactly one for sender and one for recipient. |

Additional rules:

- Owners may only be the sender and recipient.
- Duplicate owners are rejected.
- An envelope must not be supplied for a participant without active recovery.
- `recovery_key_version` must equal that owner’s current active bundle version.
- Metadata algorithm must be `recovery-box-v1` and contain a non-empty nonce.
- The server cannot prove that all envelopes contain the same plaintext content key. The client must generate one random content key and wrap that exact key for every normal and recovery envelope.

## Request

```ts
export interface SendDirectMessageRequest {
  recipient_user_id: ExternalUserId;
  sender_device_id: UUID;
  client_message_id: UUID;
  message_type: MessageType;
  encrypted_payload: Base64String;
  encryption_metadata: Record<string, unknown>;
  encryption_version: number;
  reply_to_id?: UUID | null;
  client_sent_at?: ISODateTime | null;
  envelopes: MessageKeyEnvelopeInput[];
  recovery_envelopes?: RecoveryEnvelopeInput[];
}
```

Example with both users using recovery:

```json
{
  "recipient_user_id": "2",
  "sender_device_id": "11111111-1111-4111-8111-111111111111",
  "client_message_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  "message_type": "text",
  "encrypted_payload": "<ciphertext>",
  "encryption_metadata": {
    "algorithm": "xchacha20poly1305-ietf",
    "nonce": "<payload-nonce>",
    "aad_version": 1
  },
  "encryption_version": 1,
  "reply_to_id": null,
  "client_sent_at": "2026-06-27T00:00:00Z",
  "envelopes": [
    {
      "recipient_device_id": "11111111-1111-4111-8111-111111111111",
      "protocol": "device_sync",
      "session_reference": "sender-sync-session",
      "wrapped_message_key": "<wrapped-for-sender-device>",
      "key_wrap_metadata": {
        "algorithm": "device-sync-v1",
        "nonce": "<sync-nonce>"
      },
      "envelope_version": 1
    },
    {
      "recipient_device_id": "22222222-2222-4222-8222-222222222222",
      "protocol": "double_ratchet",
      "session_reference": "recipient-ratchet-session",
      "wrapped_message_key": "<wrapped-for-recipient-device>",
      "key_wrap_metadata": {
        "algorithm": "double-ratchet-v1",
        "message_number": 1,
        "nonce": "<ratchet-wrap-nonce>"
      },
      "envelope_version": 1
    }
  ],
  "recovery_envelopes": [
    {
      "recovery_owner_user_id": "1",
      "recovery_key_version": 1,
      "wrapped_message_key": "<same-content-key-wrapped-for-user-1-recovery>",
      "key_wrap_metadata": {
        "algorithm": "recovery-box-v1",
        "nonce": "<recovery-nonce-1>"
      },
      "envelope_version": 1
    },
    {
      "recovery_owner_user_id": "2",
      "recovery_key_version": 3,
      "wrapped_message_key": "<same-content-key-wrapped-for-user-2-recovery>",
      "key_wrap_metadata": {
        "algorithm": "recovery-box-v1",
        "nonce": "<recovery-nonce-2>"
      },
      "envelope_version": 1
    }
  ]
}
```

## Success

First storage returns `201`; an exact retry returns `200`.

```ts
export interface SendDirectMessageResult {
  room_id: UUID;
  room_type: "direct";
  room_created: boolean;
  message_id: UUID;
  client_message_id: UUID;
  message_created: boolean;
  envelope_count: number;
  recovery_envelope_count: number;
  created_at: ISODateTime;
}
```

```json
{
  "success": true,
  "message": "Encrypted direct message stored successfully.",
  "data": {
    "room_id": "d10ede6c-12db-4f93-a456-e946a53cad97",
    "room_type": "direct",
    "room_created": true,
    "message_id": "71371732-ea43-435d-ad8d-6cbf80c3daaa",
    "client_message_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "message_created": true,
    "envelope_count": 2,
    "recovery_envelope_count": 2,
    "created_at": "2026-06-27T00:00:00Z"
  }
}
```

## Idempotency

Persist the complete request in an encrypted outbox before sending.

An exact retry must reuse byte-identical semantic data:

- Same `client_message_id`.
- Same ciphertext and payload nonce.
- Same normal envelopes.
- Same recovery envelopes.
- Same metadata.
- No second ratchet advancement.

A modified retry returns `409 Conflict`. Treat this as local encrypted-outbox corruption or a programming error; do not generate another variation with the same ID.

---

# 15. Retrieve device-specific room history

## `GET /api/v1/messages/rooms/{room_id}/history/`

**Status:** IMPLEMENTED + TESTED  
**Authentication:** Required  
**Pagination:** Cursor, newest first  
**Default / maximum page size:** 50 / 100

Query:

```ts
export interface EncryptedHistoryQuery {
  device_id: UUID;
  page_size?: number;
  cursor?: string;
}
```

The request succeeds only for an active room, active membership, and active device owned by the authenticated user. A message is returned only if it has a normal envelope for that device.

```ts
export interface MessageKeyEnvelopeOutput {
  recipient_user_id: ExternalUserId;
  recipient_device_id: UUID;
  protocol: EnvelopeProtocol;
  session_reference: string;
  wrapped_message_key: Base64String;
  key_wrap_metadata: Record<string, unknown>;
  envelope_version: number;
  created_at?: ISODateTime;
}

export interface EncryptedHistoryMessage {
  id: UUID;
  room_id: UUID;
  sender_user_id: ExternalUserId;
  sender_device_id: string;
  client_message_id: UUID;
  message_type: MessageType;
  encrypted_payload: Base64String;
  encryption_metadata: Record<string, unknown>;
  encryption_version: number;
  reply_to_id: UUID | null;
  client_sent_at: ISODateTime | null;
  created_at: ISODateTime;
  device_envelope: MessageKeyEnvelopeOutput;
}
```

Response:

```json
{
  "success": true,
  "message": "Encrypted message history retrieved successfully.",
  "data": {
    "room_id": "<uuid>",
    "room_type": "direct",
    "device_id": "<uuid>",
    "next": null,
    "previous": null,
    "messages": []
  }
}
```

Generic authorization failure:

```text
403 Forbidden
```

```json
{
  "success": false,
  "message": "Encrypted message history is unavailable for this room and device."
}
```

Follow the complete `next` URL. Do not reconstruct cursor values.

---


# 16. Recovery cryptographic model

Myna recovery restores message content keys; it does not restore old Double Ratchet sessions.

Client-generated recovery material:

```text
recovery keypair
   |
   +--> public key -> server
   |
   +--> private key
          |
          +--> encrypted locally with a key derived from:
                 - independent recovery key, or
                 - WebAuthn PRF, or
                 - both
          |
          +--> encrypted bundle -> server
```

For each message content key `CK`:

```text
CK -> wrap for each active device -> normal envelopes
CK -> wrap for each active recovery public key -> recovery envelopes
```

Never derive recovery directly from the account password. Maintain an independent high-entropy recovery-key fallback even when WebAuthn PRF is supported.

Recommended UI labels:

- “Encrypted cloud recovery” rather than “server backup.”
- “Recovery key” rather than “password.”
- “This browser cannot recover messages until you unlock recovery.”

---

# 17. Configure encrypted recovery

## `POST /api/v1/e2ee/recovery/setup/`

**Status:** IMPLEMENTED + TESTED  
**Authentication:** Required

```ts
export interface RecoverySetupRequest {
  recovery_public_key: Base64String;
  encrypted_recovery_private_key: Base64String;
  encryption_metadata: RecoveryBundleEncryptionMetadata;
}
```

Constraints:

- Public key max 4,096 characters.
- Encrypted private-key bundle max 65,535 characters.
- Metadata max 8 KiB serialized.
- Algorithm must be `xchacha20poly1305-ietf`.
- Metadata requires `algorithm`, `nonce`, and `unlock_method`.
- Supported unlock methods are `recovery_key`, `webauthn_prf`, and `recovery_key_and_webauthn_prf`.

Example:

```json
{
  "recovery_public_key": "<base64-public-key>",
  "encrypted_recovery_private_key": "<base64-ciphertext>",
  "encryption_metadata": {
    "algorithm": "xchacha20poly1305-ietf",
    "nonce": "<base64-24-byte-nonce>",
    "unlock_method": "recovery_key_and_webauthn_prf",
    "kdf": "hkdf-sha256",
    "bundle_schema": "myna.recovery.private-key.v1"
  }
}
```

First setup returns `201 Created`:

```json
{
  "success": true,
  "message": "Encrypted recovery configured successfully.",
  "data": {
    "recovery_version": 1,
    "is_active": true,
    "created_at": "<iso-time>",
    "updated_at": "<iso-time>",
    "rotated_at": null
  }
}
```

An already active bundle returns `409` and must be changed with the rotation endpoint.

Frontend setup wizard:

1. Explain that recovery is optional but required for restoring old cloud history on a new device.
2. Generate the recovery keypair inside the crypto worker.
3. Generate an independent high-entropy recovery key.
4. Offer WebAuthn PRF only after feature detection.
5. Derive the local bundle-encryption key.
6. Encrypt the private recovery key locally.
7. Upload only the public key and encrypted private-key bundle.
8. Show/download the independent recovery key once and require user confirmation.
9. Start backfill for old eligible messages.
10. Show coverage progress until complete.

---

# 18. Read recovery status

## `GET /api/v1/e2ee/recovery/status/`

**Status:** IMPLEMENTED + TESTED

```ts
export interface RecoveryStatusResult {
  configured: boolean;
  is_active: boolean;
  recovery_version: number | null;
  created_at: ISODateTime | null;
  updated_at: ISODateTime | null;
  rotated_at: ISODateTime | null;
  disabled_at: ISODateTime | null;
}
```

Not configured:

```json
{
  "success": true,
  "message": "Encrypted recovery status retrieved successfully.",
  "data": {
    "configured": false,
    "is_active": false,
    "recovery_version": null,
    "created_at": null,
    "updated_at": null,
    "rotated_at": null,
    "disabled_at": null
  }
}
```

Use this endpoint to drive settings UI, but never infer that the local browser currently has the recovery private key unlocked.

Keep separate frontend state:

```ts
type RecoveryServerState = "not_configured" | "active";
type RecoveryLocalUnlockState =
  | "locked"
  | "unlocking"
  | "unlocked"
  | "failed";
```

---

# 19. Download encrypted recovery bundle

## `GET /api/v1/e2ee/recovery/bundle/`

**Status:** IMPLEMENTED + TESTED  
**Owner only:** Yes

```ts
export interface RecoveryBundleResult {
  recovery_public_key: Base64String;
  encrypted_recovery_private_key: Base64String;
  encryption_metadata: RecoveryBundleEncryptionMetadata;
  recovery_version: number;
  is_active: true;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  rotated_at: ISODateTime | null;
}
```

No active bundle returns `404` with `Encrypted recovery is not available.`

The API returns ciphertext. Unlock it only inside the crypto worker. Never place the unlocked private key in React state, logs, analytics, query caches, or Redux devtools.

---

# 20. Resolve active recovery public keys

## `POST /api/v1/e2ee/recovery/public-keys/resolve/`

**Status:** IMPLEMENTED + TESTED  
**Maximum users per request:** 20

Request:

```json
{
  "user_ids": ["1", "2"]
}
```

Duplicate IDs or an empty list return `400`.

Response:

```ts
export interface ResolvedRecoveryPublicKey {
  user_id: ExternalUserId;
  recovery_public_key: Base64String;
  recovery_version: number;
  updated_at: ISODateTime;
}

export interface RecoveryPublicKeysResult {
  public_keys: ResolvedRecoveryPublicKey[];
}
```

Only active bundles are returned. Missing users are omitted; the output is ordered by user ID and is not guaranteed to match input order. Convert it to a map keyed by `user_id`.

The endpoint never returns encrypted private-key bundles or private-key metadata.

Current authorization note: any authenticated user can request up to 20 external user IDs. A future hardening step should restrict this to authorized message recipients or combine it with prekey claim authorization.

---

# 21. Recovery-aware direct-send preparation

Before encrypting a new direct message:

1. Claim/refresh normal recipient device bundles.
2. Resolve recovery public keys for sender and recipient.
3. Generate one random message content key.
4. Encrypt the payload once.
5. Wrap the same key for every active normal device.
6. Wrap the same key for every returned active recovery key.
7. Persist the complete request in the encrypted outbox.
8. Call `POST /api/v1/messages/direct/`.

Do not resolve recovery keys after ratchet state has already advanced unless the entire operation can be rolled back locally.

Cache recovery public keys only briefly and always bind them to `recovery_version`. Refresh after any version mismatch or `400` mentioning the active bundle version.

---

# 22. Retrieve encrypted recovery history

## `GET /api/v1/messages/recovery-history/`

**Status:** IMPLEMENTED + TESTED  
**Pagination:** Cursor, newest first  
**Page size:** default 50, maximum 100

No device ID is required. Authorization is possession of a recovery envelope owned by the authenticated user plus an active recovery bundle.

```ts
export interface RecoveryEnvelopeOutput {
  recovery_owner_user_id: ExternalUserId;
  recovery_key_version: number;
  wrapped_message_key: Base64String;
  key_wrap_metadata: RecoveryKeyWrapMetadata;
  envelope_version: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface RecoveryHistoryMessage {
  id: UUID;
  room_id: UUID;
  sender_user_id: ExternalUserId;
  sender_device_id: string;
  client_message_id: UUID;
  message_type: MessageType;
  encrypted_payload: Base64String;
  encryption_metadata: Record<string, unknown>;
  encryption_version: number;
  reply_to_id: UUID | null;
  client_sent_at: ISODateTime | null;
  created_at: ISODateTime;
  recovery_envelope: RecoveryEnvelopeOutput;
}
```

Response:

```json
{
  "success": true,
  "message": "Encrypted recovery history retrieved successfully.",
  "data": {
    "next": null,
    "previous": null,
    "messages": []
  }
}
```

The endpoint returns only the authenticated user’s recovery envelope. It may return history after the user leaves a room because the previously issued recovery envelope is the authorization record for that historical message.

Client flow per message:

1. Validate envelope version and owner ID.
2. Select the correct recovery private key version.
3. Locally unwrap the content key.
4. Authenticate and decrypt the payload.
5. Optionally create a new device envelope for the current device.
6. Never upload the plaintext content key.

No active recovery returns `403`.

---

# 23. Rewrap recovered keys for a new device

## `POST /api/v1/messages/recovery/rewrap/`

**Status:** IMPLEMENTED + TESTED  
**Maximum messages:** 100 per request  
**Atomic:** Yes

```ts
export interface RecoveryRewrapItem {
  message_id: UUID;
  wrapped_message_key: Base64String;
  key_wrap_metadata: DeviceSyncWrapMetadata;
  envelope_version: number;
}

export interface RecoveryRewrapRequest {
  device_id: UUID;
  envelopes: RecoveryRewrapItem[];
}
```

The target device must be active and owned by the authenticated user. Each message must already have a recovery envelope owned by that user.

Metadata algorithm must be `device-sync-v1` with a non-empty nonce.

First creation returns `201`; an exact retry returns `200`:

```json
{
  "success": true,
  "message": "Recovered message keys were wrapped for the device successfully.",
  "data": {
    "device_id": "<uuid>",
    "created_count": 50,
    "existing_count": 0,
    "total_count": 50
  }
}
```

A changed retry returns `409`. One invalid message rolls back the entire batch.

---

# 24. Find messages requiring recovery backfill

## `GET /api/v1/messages/recovery/backfill/candidates/?device_id={uuid}`

**Status:** IMPLEMENTED + TESTED  
**Pagination:** Cursor, default 50, maximum 100

Purpose: recovery may be configured after old messages already exist. This endpoint returns old messages that the selected active owned device can decrypt but that do not yet have a recovery envelope for the user.

```ts
export interface RecoveryBackfillCandidate extends Omit<
  RecoveryHistoryMessage,
  "recovery_envelope"
> {
  device_envelope: MessageKeyEnvelopeOutput;
}
```

Response:

```json
{
  "success": true,
  "message": "Recovery backfill candidates retrieved successfully.",
  "data": {
    "device_id": "<uuid>",
    "recovery_key_version": 3,
    "next": null,
    "previous": null,
    "messages": []
  }
}
```

Eligibility requires active recovery, active room, active membership, and a normal envelope for the selected active owned device. Existing recovery-covered messages are excluded.

---

# 25. Backfill recovery envelopes

## `POST /api/v1/messages/recovery/backfill/`

**Status:** IMPLEMENTED + TESTED  
**Maximum messages:** 100  
**Atomic:** Yes

```ts
export interface RecoveryBackfillItem {
  message_id: UUID;
  wrapped_message_key: Base64String;
  key_wrap_metadata: RecoveryKeyWrapMetadata;
  envelope_version: number;
}

export interface RecoveryBackfillRequest {
  device_id: UUID;
  recovery_key_version: number;
  envelopes: RecoveryBackfillItem[];
}
```

The selected device must already have a normal envelope for every submitted message. The server uses that fact plus membership to authorize backfill, but it never sees the locally unwrapped key.

First creation returns `201`; exact retry returns `200`; changed retry or stale recovery version returns `409`.

```json
{
  "success": true,
  "message": "Recovery envelopes backfilled successfully.",
  "data": {
    "device_id": "<uuid>",
    "recovery_key_version": 3,
    "created_count": 50,
    "existing_count": 0,
    "total_count": 50
  }
}
```

Recommended coordinator loop:

```text
coverage -> choose device with candidates
         -> get candidate page
         -> worker unwraps device envelope
         -> worker wraps key with recovery public key
         -> post batch
         -> follow next cursor
         -> repeat coverage
```

Pause safely when the browser locks or closes. Resume by calling coverage and candidates again; exact retries are safe.

---

# 26. Audit recovery coverage

## `GET /api/v1/messages/recovery/coverage/`

**Status:** IMPLEMENTED + TESTED  
**Read-only:** Yes

```ts
export interface RecoveryCoverageDevice {
  device_id: UUID;
  device_name: string;
  platform: DevicePlatform;
  backfill_candidate_count: number;
}

export interface RecoveryCoverageResult {
  recovery_version: number;
  total_eligible_messages: number;
  current_version_covered_messages: number;
  missing_recovery_envelopes: number;
  stale_recovery_envelopes: number;
  coverage_percent: number;
  is_complete: boolean;
  active_devices: RecoveryCoverageDevice[];
}
```

Semantics:

- Eligible means active room membership and at least one normal envelope on an active owned device.
- Missing means no recovery envelope exists for the user.
- Stale means an envelope exists but does not use the current recovery version.
- Empty eligible history is `100.0%` complete.
- `is_complete` is true only when missing and stale counts are both zero.

Use this endpoint for a recovery settings progress card. Do not claim “Recovery complete” based only on successful setup.

---

# 27. Rotate recovery keys

## `POST /api/v1/e2ee/recovery/rotate/`

**Status:** IMPLEMENTED + TESTED  
**Atomic:** Yes, all-or-nothing  
**Maximum submitted envelope list:** 5,000

Rotation replaces the bundle and every existing user-owned recovery envelope in one database transaction.

```ts
export interface RecoveryRotationEnvelope {
  message_id: UUID;
  wrapped_message_key: Base64String;
  key_wrap_metadata: RecoveryKeyWrapMetadata;
  envelope_version: number;
}

export interface RecoveryRotateRequest extends RecoverySetupRequest {
  current_recovery_version: number;
  recovery_envelopes: RecoveryRotationEnvelope[];
}
```

Requirements:

- The current version must match.
- The public key must actually change.
- Every existing recovery envelope owned by the user must be included exactly once.
- No unknown message may be included.
- Every content key must be locally unwrapped with the old private key and wrapped with the new public key.
- New server version equals `current_recovery_version + 1`.

Response is always `200` for success or exact retry:

```json
{
  "success": true,
  "message": "Encrypted recovery rotated successfully.",
  "data": {
    "recovery_version": 4,
    "rotated_envelope_count": 120,
    "rotation_applied": true,
    "rotated_at": "<iso-time>"
  }
}
```

An exact completed retry returns `rotation_applied: false`. A changed or stale retry returns `409`. Missing envelope coverage returns `400`. No active bundle returns `404`.

Important frontend constraint: the current backend expects complete rotation in one request, so the UI must not start rotation unless all recovery history can be processed and retained in memory/storage safely. For very large accounts, a future staged rotation protocol may be needed.

---

# 28. Permanently disable and delete recovery

## `DELETE /api/v1/e2ee/recovery/`

**Status:** IMPLEMENTED + TESTED  
**Idempotent:** Yes

This permanently deletes:

- Recovery bundle.
- Recovery public key.
- Encrypted recovery private-key bundle.
- Every recovery envelope owned by the user.

It preserves:

- Messages and ciphertext.
- Rooms.
- Normal device envelopes.
- Other users’ recovery data.

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

A second call returns `200` with `bundle_deleted: false`.

UI requirements:

- Use a destructive confirmation dialog.
- Explain that a future lost-device restore becomes impossible unless another trusted device still has keys.
- Require a typed confirmation phrase or local reauthentication.
- Clear the locally unlocked recovery private key after success.
- Do not delete normal local device state automatically.

---


# 29. Complete frontend workflows

## Application startup

1. Restore Identity-service session.
2. Start the crypto worker.
3. Load encrypted local device record from IndexedDB.
4. Unlock local device state.
5. Register a device only when no valid local device record exists.
6. Upload/replenish one-time prekeys.
7. Fetch room list.
8. Fetch recovery status.
9. If recovery is active, fetch coverage in the background.
10. Do not automatically unlock recovery; ask only when restore/backfill/rotation needs the private key.

## Open a conversation

1. Obtain the external recipient ID from Identity contacts/search.
2. Refresh recipient prekey bundles.
3. Verify signed prekeys and trusted identity keys.
4. Establish sessions for new devices.
5. Load room list/direct-room mapping.
6. If a room exists, request device-specific history.
7. Decrypt in the worker and return safe render models.

## Send a direct message

1. Generate `client_message_id` once.
2. Canonically serialize plaintext.
3. Generate one random content key and payload nonce.
4. Resolve active normal devices and recovery public keys.
5. Encrypt payload once.
6. Wrap the same key for every normal and recovery target.
7. Store the complete request in encrypted outbox.
8. POST direct message.
9. Commit ratchet state and outbox status according to the local transaction design.
10. Refresh/add room in room cache.
11. When WebSockets exist, reconcile the later `message.stored`/`message.new` events by IDs.

## Receive and decrypt

1. Receive history now; WebSocket event later.
2. Select only this device’s normal envelope.
3. Validate metadata and protocol version.
4. Unwrap content key locally.
5. Authenticate/decrypt payload and AAD.
6. Commit ratchet state only after successful authentication.
7. Render a plaintext view model; never cache plaintext indefinitely.

## Restore on a new device

1. Register and initialize the new device.
2. Read recovery status and download encrypted bundle.
3. Unlock recovery inside worker.
4. Fetch recovery history pages.
5. Decrypt recovery envelopes and payloads locally.
6. Build `device-sync-v1` envelopes for the new device.
7. POST rewrap batches.
8. Load normal room history with new device ID.
9. Lock recovery key when restore is complete.

## Enable recovery on an existing account

1. Setup bundle.
2. Read coverage.
3. Select an active device with backfill candidates.
4. Process candidate pages and post backfill batches.
5. Repeat until coverage is complete.
6. Surface partial progress and resumability.

## Rotate recovery

1. Unlock old recovery key.
2. Fetch complete recovery history.
3. Generate a new recovery keypair and encrypted private-key bundle.
4. Rewrap every content key to the new public key.
5. Submit one atomic rotation request.
6. Replace local recovery metadata only after `rotation_applied` success or verified exact retry.

---

# 30. Required React module structure

```text
src/
├── config/
│   └── env.ts
├── auth/
│   └── auth-session.ts
├── messenger/
│   ├── api/
│   │   ├── messenger-client.ts
│   │   ├── device.api.ts
│   │   ├── prekey.api.ts
│   │   ├── rooms.api.ts
│   │   ├── messages.api.ts
│   │   └── recovery.api.ts
│   ├── crypto/
│   │   ├── crypto.worker.ts
│   │   ├── crypto-worker-client.ts
│   │   ├── codecs/
│   │   └── protocol-types.ts
│   ├── storage/
│   │   ├── device.repository.ts
│   │   ├── ratchet.repository.ts
│   │   ├── outbox.repository.ts
│   │   └── recovery.repository.ts
│   ├── services/
│   │   ├── device-bootstrap.service.ts
│   │   ├── direct-message.service.ts
│   │   ├── history-decrypt.service.ts
│   │   ├── recovery-setup.service.ts
│   │   ├── recovery-restore.service.ts
│   │   ├── recovery-backfill.service.ts
│   │   └── recovery-rotation.service.ts
│   ├── state/
│   │   ├── room.store.ts
│   │   ├── message.store.ts
│   │   ├── outbox.store.ts
│   │   └── recovery.store.ts
│   ├── hooks/
│   │   ├── useDeviceBootstrap.ts
│   │   ├── useRooms.ts
│   │   ├── useEncryptedHistory.ts
│   │   ├── useSendEncryptedMessage.ts
│   │   ├── useRecoveryStatus.ts
│   │   ├── useRecoveryCoverage.ts
│   │   └── useRecoveryCoordinator.ts
│   └── ui/
│       ├── conversations/
│       ├── composer/
│       ├── messages/
│       └── recovery/
└── shared/
```

UI components must issue commands to services. They must not directly perform cryptography or manipulate private keys.

Suggested recovery UI:

- `RecoverySettingsCard`
- `RecoverySetupWizard`
- `RecoveryKeyConfirmation`
- `RecoveryUnlockDialog`
- `RecoveryCoverageProgress`
- `RecoveryRestoreProgress`
- `RecoveryRotationWizard`
- `DisableRecoveryDialog`

---

# 31. Required strict-E2EE cryptographic design

## Do not invent a custom messaging protocol

Use an audited implementation compatible with the Signal protocol specifications wherever possible.

The current backend data model expects:

- Public identity and prekey bundles.
- Pairwise sessions.
- Double Ratchet recipient envelopes.
- Device-sync sender envelopes.
- One ciphertext payload encrypted once.
- One wrapped content key per authorized device.

## Recommended primitive profile

| Purpose | Recommended profile |
|---|---|
| Identity agreement | X25519 |
| Identity signing | Ed25519 or library-managed Signal-compatible identity signatures |
| Initial asynchronous session | X3DH or PQXDH-compatible flow |
| Ongoing pairwise session | Double Ratchet |
| KDF | HKDF-SHA-256 |
| Payload AEAD | XChaCha20-Poly1305-IETF |
| Payload key | Random 32 bytes |
| Payload nonce | Random 24 bytes |
| Key-envelope wrapping | AEAD using a unique ratchet-derived wrapping key |
| Hashing/canonical IDs | SHA-256 |
| Randomness | OS/browser CSPRNG only |

## Important distinction

Libsodium primitives are not a complete Signal protocol implementation.

XChaCha20-Poly1305 can provide authenticated encryption, but it does not by itself provide:

- Asynchronous session establishment.
- Forward secrecy across messages.
- Post-compromise recovery.
- Out-of-order message handling.
- Identity-change handling.
- Multi-device session management.

Those properties come from X3DH/PQXDH, Double Ratchet, and a multi-device session manager.

## Content-key envelope design

For each message:

```text
plaintext
   |
   | random content key CK
   v
XChaCha20-Poly1305
   |
   +--> encrypted_payload
   +--> payload nonce and versioned metadata

CK
   |
   +--> wrapped with recipient-device Double Ratchet message key
   |       -> double_ratchet envelope
   |
   +--> wrapped with sender-device sync session key
           -> device_sync envelope
```

The server never receives:

- Plaintext.
- Content key.
- Ratchet message key.
- Root key.
- Chain key.
- Identity private key.
- Signed-prekey private key.
- One-time-prekey private key.
- Device-sync private key.

---

# 32. Canonical plaintext format

Do not encrypt arbitrary JavaScript objects directly.

Create a versioned canonical payload:

```ts
export interface EncryptedTextContentV1 {
  schema: "myna.message.text";
  version: 1;
  text: string;
  mentions?: ExternalUserId[];
}
```

Example before encryption:

```json
{
  "schema": "myna.message.text",
  "version": 1,
  "text": "Hello",
  "mentions": []
}
```

Serialize with one deterministic canonical JSON implementation. Every client platform must produce compatible bytes.

Encoding:

```text
UTF-8 canonical JSON
```

---

# 33. Associated data

AEAD associated data binds ciphertext to important routing fields so the server cannot silently transplant ciphertext between contexts.

Recommended version 1:

```ts
export interface MessageAssociatedDataV1 {
  schema: "myna.message.aad";
  version: 1;
  room_id: UUID | null;
  sender_user_id: ExternalUserId;
  sender_device_id: UUID;
  recipient_user_id: ExternalUserId;
  client_message_id: UUID;
  message_type: MessageType;
  reply_to_id: UUID | null;
  encryption_version: number;
}
```

For the first message, `room_id` is not yet known. Use `null` and bind to the direct participant IDs. Do not change AAD on retry.

The exact AAD encoding must be versioned and shared by all clients.

---

# 34. Browser key storage

## Never store private keys in

- `localStorage`.
- `sessionStorage`.
- Redux persistence.
- React state.
- URL query strings.
- Logs.
- Error-reporting payloads.
- Analytics events.
- Server databases.

## Recommended structure

- Run cryptography in a dedicated Web Worker.
- Keep unwrapped private keys only inside worker memory.
- Store encrypted key/state blobs in IndexedDB.
- Use a non-extractable local wrapping key where browser support allows it.
- Require a local unlock step for sensitive state.
- Clear worker memory references on logout and lock.
- Use Web Locks or another single-writer mechanism for ratchet-state updates.
- Use `BroadcastChannel` only for non-secret coordination between tabs.
- Never send private key material through `BroadcastChannel`.

## XSS warning

E2EE does not protect against malicious JavaScript running in the same origin.

Production requirements include:

- Strict Content Security Policy.
- No untrusted inline scripts.
- Minimal third-party JavaScript.
- Dependency pinning and lockfiles.
- Subresource integrity where applicable.
- No rendering of unsanitized HTML.
- Trusted Types where practical.
- Security review of browser extensions and Electron wrappers.

---

# 35. Ratchet-state transaction rules

## Sending

The following must be one logical local transaction:

1. Load ratchet state.
2. Derive one message/wrapping key.
3. Advance ratchet.
4. Build envelope.
5. Store advanced state.
6. Store exact encrypted outbox request.

If local persistence fails, do not send.

On network retry, reuse the outbox request. Do not derive another ratchet key.

## Receiving

The following must be one logical local transaction:

1. Load ratchet state.
2. Locate/derive the message key.
3. Authenticate and decrypt the wrapped content key.
4. Authenticate and decrypt payload.
5. Advance ratchet and remove consumed skipped key.
6. Store state.
7. Mark message decrypted.

If authentication fails, discard state changes.

The Double Ratchet specification explicitly requires state changes to be discarded when message authentication fails.

---

# 36. Multi-device and cloud-recovery requirements

The backend requires an envelope for every active device.

Therefore the frontend must maintain:

```ts
export interface UserDeviceDirectory {
  userId: ExternalUserId;
  devices: Array<{
    deviceId: UUID;
    identityKey: Base64String;
    sessionState: "missing" | "ready" | "identity_changed";
  }>;
}
```

Before sending:

- Refresh or claim recipient bundles.
- Identify all active recipient devices.
- Identify all active sender devices.
- Create exactly one envelope for each.
- Do not silently omit an unfamiliar device.
- Do not send when an identity change requires user review.

## New device and old history

A newly registered device does not automatically have normal device envelopes for old messages. The implemented recovery flow solves this without exposing plaintext keys:

1. Register the new device and securely persist its private device state locally.
2. Read recovery status.
3. Download the encrypted recovery bundle.
4. Ask the user to unlock the recovery private key locally using the independent recovery key, WebAuthn PRF, or the configured combined method.
5. Fetch `GET /api/v1/messages/recovery-history/`.
6. Locally unwrap each message content key from its recovery envelope.
7. Locally wrap the same content key for the new device with `device-sync-v1`.
8. Upload those device envelopes through `POST /api/v1/messages/recovery/rewrap/` in batches of at most 100.
9. Load normal room history using the new `device_id`.

The server never receives the unlocked recovery private key or plaintext message content keys.

---

# 36A. Device-sync protocol

`device_sync` is separate from recipient Double Ratchet delivery.

Recommended design:

- Each pair of the user's devices has an authenticated pairwise sync session, or
- The account has a carefully designed device-group sync key with rotation and membership controls.

Do not use a static account-wide key forever.

A device-sync envelope should include:

- Sync protocol version.
- Sender device ID.
- Recipient device ID.
- Session or epoch ID.
- Unique nonce.
- Wrapped content key.
- Authenticated metadata.
- Key-rotation information where applicable.

Device linking must verify the new device through a trusted existing device, QR transfer, or passkey-backed process.

---


# 37. Near-future WebSocket architecture for instant delivery

## Current state

WebSockets are **not implemented yet**. The frontend must work fully using REST first.

REST remains the durable source of truth for:

- Message storage and exact retries.
- Room list.
- Device-specific history.
- Recovery history.
- Backfill, coverage, rotation, and restore.
- Reconciliation after disconnect.

## Planned stack

- Django Channels.
- Redis channel layer.
- One authenticated socket per logged-in browser device.
- WSS in production.

Recommended path:

```text
wss://messenger.example.com/ws/v1/messenger/
```

Do not open one permanent socket per room.

## Authentication plan

Browser WebSocket APIs cannot attach a normal Authorization header. Add a future short-lived ticket endpoint:

```http
POST /api/v1/realtime/tickets/
Authorization: Bearer <access-token>
```

The ticket should be random, single-use, expire in 30–60 seconds, and be bound to the authenticated user and device.

Handshake:

```text
wss://messenger.example.com/ws/v1/messenger/?ticket=<single-use-ticket>
```

Do not place the long-lived access token in the WebSocket query string.

## Planned event model

```ts
export interface RealtimeEvent<TType extends string, TPayload> {
  event_id: UUID;
  type: TType;
  version: 1;
  occurred_at: ISODateTime;
  payload: TPayload;
}
```

Initial events:

- `connection.hello`
- `connection.accepted`
- `room.subscribe`
- `room.unsubscribe`
- `message.send`
- `message.stored`
- `message.new`
- `room.updated`

Later events:

- `receipt.delivered`
- `receipt.read`
- `typing.start`
- `typing.stop`
- `presence.update`
- `device.bundle.changed`

## Critical message rule

`message.send` must use the exact same payload as `SendDirectMessageRequest`, including recovery envelopes. The consumer must call the same domain service as REST and enforce the same ownership, envelope, recovery-version, idempotency, and atomicity rules.

The recipient `message.new` event must contain ciphertext and only the receiving device’s normal envelope. It must never broadcast all device envelopes or other users’ recovery envelopes.

## Reconnect strategy

1. Reauthenticate with a fresh ticket.
2. Resubscribe to active room/user streams.
3. Fetch REST room history to recover missed messages.
4. Deduplicate by `message_id` and `client_message_id`.
5. Do not assume WebSocket delivery is durable.
6. Persist before broadcast and use `transaction.on_commit`.

## Heartbeats and backpressure

- Heartbeat every 20–30 seconds.
- Exponential reconnect with jitter.
- Maximum event size and queue length.
- Rate-limit ephemeral events.
- Close on invalid JSON/version.
- Never silently drop stored-message acknowledgements.

---

# 38. Error handling matrix

| Status | Meaning | Frontend action |
|---|---|---|
| `400` | Invalid fields, missing/extra envelope, wrong owner/protocol/version | Do not retry blindly; refresh device/recovery state and fix request. |
| `401` | Invalid or expired Identity token | Clear auth, lock crypto worker, return to login. |
| `403` | Generic room/device/recovery authorization failure | Do not reveal guessed resource existence. |
| `404` | Active recovery bundle unavailable for bundle/rotation | Refresh recovery status. |
| `409` | Idempotency mismatch, stale recovery version, changed retry | Stop mutation; reload server state and inspect local encrypted operation. |
| `429` | Rate limiting | Back off without regenerating crypto. |
| `5xx` | Server failure | Keep exact encrypted outbox/batch request and retry safely. |

Never regenerate ciphertext or advance a ratchet merely because transport failed.

---

# 39. Remaining backend blockers for a complete chat product

- Device list, rename, and revoke APIs.
- Direct-room resolve endpoint before first send.
- Identity-service contact/block authorization in Messenger.
- Realtime ticket endpoint and Channels consumers.
- Delivery/read receipt models.
- Attachment encryption/upload APIs.
- Group room APIs and sender-key E2EE.
- Scalable staged recovery rotation for accounts beyond the current 5,000-envelope request limit.

Codex must not silently create frontend calls for these planned APIs.

---

# 40. Security acceptance criteria

- [ ] Private keys are generated only on the client.
- [ ] Plaintext messages never enter REST or future WebSocket payloads.
- [ ] Recovery private key is encrypted before upload.
- [ ] Recovery key / PRF output never leaves the client.
- [ ] One content key is wrapped consistently for all normal and recovery targets.
- [ ] Every active normal device gets exactly one normal envelope.
- [ ] Recovery-envelope matrix is followed exactly.
- [ ] Signed prekeys and identity changes are verified.
- [ ] Ratchet state and outbox persistence are atomic.
- [ ] Exact retries reuse identical encrypted data.
- [ ] Failed authentication does not advance state.
- [ ] Room history exposes only the requesting device envelope.
- [ ] Recovery history exposes only the authenticated user recovery envelope.
- [ ] Backfill and rewrap happen locally without plaintext-key upload.
- [ ] Recovery completeness is based on coverage endpoint, not setup success.
- [ ] Disable recovery uses destructive confirmation.
- [ ] WebSocket uses WSS and a short-lived single-use ticket.
- [ ] WebSocket send reuses the REST domain service.
- [ ] XSS defenses and strict CSP are enabled.

---

# 41. Codex implementation order

## Phase A — Typed API layer

1. Build environment loader and authenticated client.
2. Add runtime schemas for all implemented responses.
3. Add device/prekey adapters.
4. Add rooms, direct send, and history adapters.
5. Add all recovery adapters.
6. Normalize errors and cursor links.

## Phase B — Secure local device

1. IndexedDB repositories.
2. Crypto Web Worker.
3. Device identity, signed prekey, and one-time prekeys.
4. Encrypted ratchet/device-sync persistence.
5. Device bootstrap and lock/logout lifecycle.

## Phase C — Direct messaging

1. Pairwise session establishment.
2. Canonical plaintext/AAD codec.
3. Payload encryption and per-device wrapping.
4. Recovery public-key resolution and recovery wrapping.
5. Encrypted outbox and exact retry.
6. History decrypt/render pipeline.

## Phase D — Recovery UI

1. Status/settings UI.
2. Setup and recovery-key confirmation.
3. Coverage and backfill coordinator.
4. New-device restore and rewrap.
5. Rotation wizard.
6. Permanent disable flow.

## Phase E — WebSocket later

Begin only after the REST and crypto workflows pass tests. Add realtime ticket, Channels + Redis, encrypted message events, and REST reconciliation.

## Codex must not

- Invent backend fields or routes.
- Put private keys in localStorage, React state, logs, or analytics.
- Perform cryptography inside components.
- Derive recovery from the account password.
- Send plaintext content keys during backfill/rewrap/rotation.
- Re-encrypt on retry.
- Treat TLS as E2EE.
- Ignore sender devices, recipient devices, or recovery versions.
- Add WebSockets before REST correctness.

---

# 42. Frontend test requirements

## API adapters

- Auth header and `401` logout behavior.
- Validation-error normalization.
- Cursor URL handling.
- Direct-send `201`, exact retry `200`, changed retry `409`.
- Recovery setup/status/bundle/public-key adapters.
- Recovery history/rewrap/backfill/coverage/rotation/delete adapters.

## Crypto and outbox

- Fresh messages use unique keys/nonces.
- Exact retry request is semantically identical.
- Tampered ciphertext, AAD, and envelopes fail.
- Ratchet state is not committed on failed authentication.
- Same content key is used for every target envelope.
- Recovery bundle cannot unlock with wrong recovery material.

## Recovery orchestration

- Setup does not claim complete coverage.
- Backfill resumes after interruption.
- Stale recovery versions cause refresh, not blind retry.
- Rewrap creates new-device envelopes without uploading plaintext keys.
- Rotation does not replace local metadata before server success.
- Disable clears unlocked recovery state.

## Future WebSocket

- Ticket single-use/expiry.
- Membership validation before subscription.
- Persist-before-broadcast.
- Device-specific envelope delivery.
- Reconnect and REST reconciliation.
- Live/history deduplication.

---

# 43. References

- Signal Double Ratchet: https://signal.org/docs/specifications/doubleratchet/
- Signal X3DH: https://signal.org/docs/specifications/x3dh/
- Signal Sesame: https://signal.org/docs/specifications/sesame/
- libsignal: https://github.com/signalapp/libsignal
- Libsodium XChaCha20-Poly1305: https://doc.libsodium.org/secret-key_cryptography/aead/chacha20-poly1305/xchacha20-poly1305_construction
- Django Channels authentication: https://channels.readthedocs.io/en/stable/topics/authentication.html
- Django Channels channel layers: https://channels.readthedocs.io/en/stable/topics/channel_layers.html
- Web Cryptography API: https://www.w3.org/TR/webcrypto/
- Web Authentication API: https://www.w3.org/TR/webauthn-3/

---

# 44. Final implementation summary

The Messenger backend now provides a tested REST foundation for strict direct-message E2EE and encrypted cloud recovery:

- Device and prekey lifecycle.
- Direct-room and room-list behavior.
- One ciphertext per message.
- Per-device normal envelopes.
- Per-user recovery envelopes.
- Device-filtered history.
- Recovery setup, download, restore, rewrap, backfill, coverage, rotation, and deletion.
- Atomicity and idempotency protections.

The React frontend must provide the local security engine and the user experience around it. The server cannot validate plaintext equivalence between different encrypted envelopes without breaking E2EE, so correct client orchestration is essential.

In the near future, Myna will add Django Channels + Redis WebSockets for instant message delivery. Those events will carry the same ciphertext contracts and will always be reconciled against durable REST history and recovery APIs.
