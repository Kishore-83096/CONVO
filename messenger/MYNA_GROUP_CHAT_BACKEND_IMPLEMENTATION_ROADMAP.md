# Myna Messenger Service
## Complete E2EE Group Chat Backend, REST API, Testing, Frontend, and WebSocket Implementation Roadmap

**Document role:** Codex implementation contract  
**Service:** Existing Django Messenger service  
**Group-chat architecture:** New Django apps/modules inside the existing Messenger service, not a new microservice  
**Current verified baseline:** 94 direct-chat, device, history, and recovery tests passing  
**Primary objective:** Add production-oriented strict E2EE group chat without breaking the working direct-chat implementation

---

# 1. How Codex must use this document

Implement one phase at a time. For every phase Codex must:

1. Inspect the actual repository before editing.
2. Preserve existing direct-chat APIs and response contracts.
3. Add or update only the files listed for that phase unless a dependency requires another file.
4. Create migrations only when models or constraints change.
5. Run targeted phase tests.
6. Run the entire Messenger test suite.
7. Fix regressions before beginning the next phase.
8. Update API documentation after any public-contract change.
9. Never send or store plaintext messages, attachment data, message keys, sender-key secrets, device private keys, recovery private keys, or ratchet state on the server.
10. Never treat WebSocket delivery as authoritative. REST and the database remain the source of truth.

This roadmap separates group-chat concerns from direct-chat concerns. Shared infrastructure is reused only where the security semantics are truly common.

---

# 2. Non-negotiable architecture decisions

## 2.1 Group chat stays inside the Messenger service

Do not create a separately deployed group-chat service.

```text
Myna React frontend
        |
        | Identity JWT
        v
Django Messenger service
├── direct chat
├── group chat
├── device/prekey management
├── cloud recovery
├── encrypted attachments
└── realtime WebSocket delivery
```

`apps/group_chat` and `apps/realtime` are Django applications inside the existing Messenger project.

## 2.2 App ownership after group implementation

| App | Authority |
|---|---|
| `apps/rooms` | Shared room and membership records for direct and group rooms. |
| `apps/chat_messages` | Shared encrypted message records, direct/group send and history, receipts, attachments and recovery envelopes. |
| `apps/e2ee_devices` | Devices, prekeys, pairwise bootstrap, recovery bundles and recovery public keys. |
| `apps/group_chat` | Group metadata, roles, epochs, sender keys, sender-key distributions and group authorization. |
| `apps/realtime` | WebSocket tickets, consumers, event publication and REST reconciliation hints. |

## 2.3 Do not rewrite direct chat

These current APIs must remain functional:

```http
POST /api/v1/e2ee/devices/register/
POST /api/v1/e2ee/devices/{device_id}/prekeys/
POST /api/v1/e2ee/prekey-bundles/claim/

GET  /api/v1/messages/rooms/
POST /api/v1/messages/direct/
GET  /api/v1/messages/rooms/{room_id}/history/

POST /api/v1/e2ee/recovery/setup/
GET  /api/v1/e2ee/recovery/status/
GET  /api/v1/e2ee/recovery/bundle/
POST /api/v1/e2ee/recovery/public-keys/resolve/
POST /api/v1/e2ee/recovery/rotate/
DELETE /api/v1/e2ee/recovery/

GET  /api/v1/messages/recovery-history/
POST /api/v1/messages/recovery/rewrap/
GET  /api/v1/messages/recovery/backfill/candidates/
POST /api/v1/messages/recovery/backfill/
GET  /api/v1/messages/recovery/coverage/
```

Existing direct rules remain unchanged:

- one encrypted payload;
- sender-device envelopes use `device_sync`;
- recipient-device envelopes use `double_ratchet`;
- idempotency is authenticated sender plus `client_message_id`;
- exact retry returns the existing message;
- changed retry returns `409 Conflict`;
- device-filtered history returns only messages with an envelope for the requested active owned device;
- recovery cryptography remains client-side.

## 2.4 Group cryptography uses sender keys

Do not create one encrypted copy of every group message for every device.

```text
Each sender device
    |
    | owns one sender key for one group epoch
    v
Encrypt group message once
    |
    | sender key is distributed separately to authorized devices
    v
Authorized devices decrypt the same ciphertext
```

Each device is an independent sender. A user's phone and browser have different sender keys.

## 2.5 Epochs enforce membership changes

```text
Epoch 1: Alice, Bob, Carol
Carol removed
Epoch 2: Alice, Bob
```

Carol may retain access to epoch-1 material she legitimately received. She must never receive epoch-2 sender keys.

## 2.6 Server versus client responsibilities

The server validates:

- membership and role;
- active device ownership;
- current epoch;
- sender-key ownership;
- distribution coverage;
- chain-iteration monotonicity;
- idempotency;
- recovery-envelope ownership;
- group-history boundaries.

The client performs:

- key generation;
- pairwise sender-key wrapping;
- group encryption/decryption;
- signatures;
- recovery wrapping/unwrapping;
- attachment encryption/decryption.

---

# 3. Current verified baseline

The current Messenger backend has **94 passing tests** covering devices, direct messaging, history and recovery.

Capture the baseline before group work:

```powershell
python manage.py check

python manage.py test `
  apps.e2ee_devices.tests `
  apps.chat_messages.tests `
  -v 2
```

Expected before group development:

```text
94 tests passed
```

If the repository has gained more tests, use the actual larger passing count. Never delete tests to restore an old number.

---

# 4. Current Messenger backend folder structure

This is the current known structure. Standard Django files and migrations may also exist.

```text
messenger/
├── manage.py
├── requirements.txt
├── messenger_config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   ├── wsgi.py
│   └── authentication.py
└── apps/
    ├── rooms/
    │   ├── apps.py
    │   ├── models.py
    │   ├── migrations/
    │   └── tests/
    ├── e2ee_devices/
    │   ├── models.py
    │   ├── serializers.py
    │   ├── services.py
    │   ├── views.py
    │   ├── urls.py
    │   ├── recovery_serializers.py
    │   ├── recovery_services.py
    │   ├── recovery_views.py
    │   ├── recovery_public_key_serializers.py
    │   ├── recovery_public_key_views.py
    │   ├── recovery_rotation_serializers.py
    │   ├── recovery_rotation_services.py
    │   ├── recovery_rotation_views.py
    │   ├── migrations/
    │   └── tests/
    └── chat_messages/
        ├── models.py
        ├── serializers.py
        ├── services.py
        ├── views.py
        ├── urls.py
        ├── recovery_serializers.py
        ├── recovery_services.py
        ├── recovery_views.py
        ├── recovery_send_serializers.py
        ├── recovery_send_services.py
        ├── recovery_backfill_serializers.py
        ├── recovery_backfill_services.py
        ├── recovery_backfill_views.py
        ├── recovery_coverage_services.py
        ├── recovery_coverage_views.py
        ├── migrations/
        └── tests/
```

## 4.1 Current frontend module structure

```text
src/
├── config/env.ts
├── auth/auth-session.ts
└── messenger/
    ├── api/
    │   ├── messenger-client.ts
    │   ├── device.api.ts
    │   ├── prekey.api.ts
    │   ├── rooms.api.ts
    │   ├── messages.api.ts
    │   └── recovery.api.ts
    ├── crypto/
    │   ├── crypto.worker.ts
    │   ├── crypto-worker-client.ts
    │   ├── codecs/
    │   └── protocol-types.ts
    ├── storage/
    │   ├── device.repository.ts
    │   ├── ratchet.repository.ts
    │   ├── outbox.repository.ts
    │   └── recovery.repository.ts
    ├── services/
    │   ├── device-bootstrap.service.ts
    │   ├── direct-message.service.ts
    │   ├── history-decrypt.service.ts
    │   ├── recovery-setup.service.ts
    │   ├── recovery-restore.service.ts
    │   ├── recovery-backfill.service.ts
    │   └── recovery-rotation.service.ts
    ├── state/
    ├── hooks/
    └── ui/
```

---

# 5. Target backend structure

Files are added gradually by the phases below.

```text
apps/
├── rooms/
│   ├── models.py
│   ├── selectors.py
│   └── tests/
├── e2ee_devices/
│   ├── existing direct/recovery files
│   ├── group_device_hooks.py
│   └── tests/
├── group_chat/
│   ├── apps.py
│   ├── constants.py
│   ├── models.py
│   ├── permissions.py
│   ├── selectors.py
│   ├── urls.py
│   ├── serializers/
│   │   ├── groups.py
│   │   ├── memberships.py
│   │   ├── epochs.py
│   │   └── sender_keys.py
│   ├── services/
│   │   ├── groups.py
│   │   ├── memberships.py
│   │   ├── epochs.py
│   │   ├── sender_keys.py
│   │   ├── distributions.py
│   │   └── security_transitions.py
│   ├── views/
│   │   ├── groups.py
│   │   ├── memberships.py
│   │   ├── epochs.py
│   │   └── sender_keys.py
│   ├── migrations/
│   └── tests/
├── chat_messages/
│   ├── existing direct/recovery files
│   ├── access_selectors.py
│   ├── group_serializers.py
│   ├── group_services.py
│   ├── group_views.py
│   ├── group_history_serializers.py
│   ├── group_history_services.py
│   ├── group_history_views.py
│   ├── group_recovery_serializers.py
│   ├── group_recovery_services.py
│   ├── receipt_*.py
│   ├── attachment_*.py
│   └── tests/
└── realtime/
    ├── authentication.py
    ├── consumers.py
    ├── events.py
    ├── publishers.py
    ├── routing.py
    ├── services.py
    ├── views.py
    ├── urls.py
    └── tests/
```

---

# 6. Shared model and transaction rules

## 6.1 External user IDs

Identity owns users. Messenger stores normalized string user IDs from JWT `sub`. Do not create local user foreign keys for group membership, audit actors, senders or recovery owners.

## 6.2 Shared Room

The existing `Room` stays authoritative.

```text
Room
- id
- room_type: direct | group
- name
- created_by_user_id
- direct_pair_key
- is_active
- created_at
- updated_at
```

Rules:

- `direct_pair_key` is direct-only;
- group rooms use `room_type="group"`;
- direct room creation remains automatic through direct send;
- group creation is explicit;
- group-specific metadata is stored in `GroupProfile`.

## 6.3 Shared RoomMember

Use the existing `RoomMember` table. Group roles are `owner`, `admin`, `member`. Group lifecycle fields must remain nullable for existing direct rows.

## 6.4 Shared Message

The existing `Message` remains the ciphertext record. Group encryption data goes into a one-to-one `GroupMessageEncryption` model.

## 6.5 Database portability

Migrations must work on local MySQL and production PostgreSQL/Neon.

## 6.6 Concurrency

Use `transaction.atomic()` and `select_for_update()` for ownership transfer, member removal, epoch rotation, sender-key registration, distributions, chain iteration, idempotent send, recovery envelopes and receipt transitions.

---

# 7. Phase summary

| Phase | Backend result | Frontend result |
|---|---|---|
| 1 | Group app scaffold and regression guard | Group module skeleton |
| 2 | Group create/list/detail/update | Group creation/info UI |
| 3 | Membership, roles, ownership, leave/ban | Member management UI |
| 4 | Permissions, audit and unified room list | Direct/group room list |
| 5 | Encryption epochs | Group security state |
| 6 | Sender-key registration | Local sender-key creation |
| 7 | Device roster and key distribution | Distribution coordinator |
| 8 | Encrypted group send | Group composer/outbox |
| 9 | Group encrypted history | Fetch/decrypt history |
| 10 | Automatic rotations | Key-refresh UX |
| 11 | Group recovery | Restore/backfill/coverage |
| 12 | Receipts, attachments, message events | Complete group UI |
| 13 | WebSockets and Redis | Instant delivery/reconcile |
| 14 | Hardening/deployment/docs | Production readiness |

---

# 8. Phase 1 — Scaffold group modules and lock the direct baseline

## Goal

Create group folders and a test harness without changing runtime behavior or schema.

## Backend changes

```text
apps/group_chat/
├── __init__.py
├── apps.py
├── constants.py
├── models.py
├── permissions.py
├── selectors.py
├── urls.py
├── serializers/__init__.py
├── services/__init__.py
├── views/__init__.py
├── migrations/__init__.py
└── tests/
    ├── __init__.py
    ├── factories.py
    └── test_group_scaffold.py
```

Update `messenger_config/settings.py` and `messenger_config/urls.py` to install and include the app. The initial `urlpatterns` may be empty.

## Constants

Define stable constants for room type, roles, member limit and epoch-rotation reasons. Do not scatter literal strings across services.

## Tests

Prove:

- app loads;
- URL namespace loads;
- `manage.py check` passes;
- existing direct routes resolve;
- all current tests remain green.

## Commands

```powershell
python manage.py check
python manage.py test apps.group_chat.tests.test_group_scaffold -v 2
python manage.py test apps.e2ee_devices.tests apps.chat_messages.tests apps.group_chat.tests -v 2
```

## Frontend changes

```text
src/messenger/
├── api/groups.api.ts
├── api/group-keys.api.ts
├── api/group-messages.api.ts
├── crypto/group/group-protocol-types.ts
├── storage/group-key.repository.ts
├── storage/group-epoch.repository.ts
├── services/groups/
├── state/group.store.ts
├── hooks/groups/
└── ui/groups/
```

Only create boundaries and types. Do not implement cryptography.

## Acceptance criteria

- no migration;
- no public group behavior;
- direct baseline unchanged;
- private keys never enter React state.

---

# 9. Phase 2 — Group room metadata and core CRUD APIs

## Goal

Create group rooms explicitly while reusing `Room` and `RoomMember`.

## Model

Add `GroupProfile` in `apps/group_chat/models.py`:

```text
GroupProfile
- id: UUID
- room: one-to-one Room
- description: optional
- avatar_storage_key: optional
- created_by_user_id
- max_members
- join_history_visible: default false
- only_admins_can_send: default false
- only_admins_can_edit_info: default true
- created_at
- updated_at
```

Group metadata is server-visible in the first version. Do not call it E2EE content.

## Files

```text
apps/group_chat/
├── models.py
├── serializers/groups.py
├── services/groups.py
├── views/groups.py
├── urls.py
├── migrations/00xx_group_profile.py
└── tests/test_group_api.py

messenger_config/identity_client.py
```

## APIs

```http
POST  /api/v1/groups/
GET   /api/v1/groups/
GET   /api/v1/groups/{group_id}/
PATCH /api/v1/groups/{group_id}/
```

Create request:

```json
{
  "name": "Backend Engineering",
  "description": "Myna backend team",
  "member_user_ids": ["2", "3"],
  "max_members": 100,
  "join_history_visible": false,
  "only_admins_can_send": false,
  "only_admins_can_edit_info": true
}
```

Create transaction:

1. normalize authenticated user ID;
2. validate fields and member limits;
3. validate users through Identity batch API before DB locks;
4. create `Room(room_type="group")`;
5. create `GroupProfile`;
6. create owner `RoomMember`;
7. create initial members;
8. commit atomically.

The creator is always owner. Sending is not available yet.

## Tests

Cover authentication, owner creation, duplicate IDs, unknown users, maximum size, rollback, list/detail access, metadata permission, inactive group and direct-room regression.

## Frontend

```text
src/messenger/
├── api/groups.api.ts
├── services/groups/group-room.service.ts
├── hooks/groups/useGroups.ts
├── hooks/groups/useCreateGroup.ts
├── hooks/groups/useGroupDetail.ts
└── ui/groups/
    ├── CreateGroupDialog.tsx
    ├── GroupInfoPanel.tsx
    └── GroupListItem.tsx
```

Select users through Identity/contact search and submit external IDs. Do not display “secure group ready” yet.

---

# 10. Phase 3 — Membership, roles, ownership and leave

## Goal

Implement complete membership lifecycle.

## RoomMember changes

Add nullable fields where absent:

```text
joined_at
left_at
removed_at
banned_at
added_by_user_id
removed_by_user_id
membership_version
```

Group roles:

```text
owner
admin
member
```

Exactly one active owner must exist per active group.

## APIs

```http
GET    /api/v1/groups/{group_id}/members/
POST   /api/v1/groups/{group_id}/members/
DELETE /api/v1/groups/{group_id}/members/{user_id}/
PATCH  /api/v1/groups/{group_id}/members/{user_id}/role/
POST   /api/v1/groups/{group_id}/leave/
POST   /api/v1/groups/{group_id}/transfer-ownership/
POST   /api/v1/groups/{group_id}/members/{user_id}/ban/
POST   /api/v1/groups/{group_id}/members/{user_id}/unban/
```

## Role rules

Owner can manage all roles, transfer ownership and ban/unban. Admin can manage normal members but never the owner. Member can view and leave. Owner must transfer ownership before leaving.

## Ownership transfer transaction

1. lock group and active owner;
2. confirm target is active member;
3. demote old owner to admin;
4. promote target to owner;
5. increment membership versions;
6. commit.

## Files

```text
apps/rooms/models.py
apps/rooms/migrations/00xx_roommember_group_lifecycle.py
apps/group_chat/serializers/memberships.py
apps/group_chat/services/memberships.py
apps/group_chat/views/memberships.py
apps/group_chat/tests/test_membership_api.py
```

## Tests

Cover owner/admin/member permission matrix, duplicate add, reactivation, bans, concurrent size limit, ownership transfer, owner leave, cross-group access and direct membership regression.

## Frontend

```text
src/messenger/
├── services/groups/group-membership.service.ts
├── hooks/groups/useGroupMembers.ts
├── hooks/groups/useManageGroupMembers.ts
└── ui/groups/
    ├── GroupMembersPanel.tsx
    ├── AddGroupMembersDialog.tsx
    ├── MemberRoleMenu.tsx
    ├── TransferOwnershipDialog.tsx
    ├── LeaveGroupDialog.tsx
    └── BanMemberDialog.tsx
```

Backend remains authoritative even when controls are hidden.

---

# 11. Phase 4 — Central permissions, audit and room-list synchronization

## Goal

Centralize authorization and make the current room list support group rooms without breaking direct output.

## Model

Add `GroupAuditEvent`:

```text
GroupAuditEvent
- id
- group_room
- actor_user_id
- event_type
- target_user_id: optional
- metadata: JSON
- created_at
```

Never log plaintext messages or secret key material.

## Permission functions

```python
can_view_group(...)
can_update_group(...)
can_add_members(...)
can_remove_member(...)
can_change_role(...)
can_transfer_ownership(...)
can_send_group_message(...)
can_manage_sender_keys(...)
can_read_group_history(...)
```

Views must not duplicate role checks.

## Selectors

Add reusable reads in `apps/group_chat/selectors.py` and `apps/chat_messages/access_selectors.py`.

## Existing room list

Keep:

```http
GET /api/v1/messages/rooms/
```

Use `room_type` as a discriminant. Add optional group data while preserving direct fields:

```json
{
  "id": "uuid",
  "room_type": "group",
  "name": "Backend Engineering",
  "is_active": true,
  "group": {
    "caller_role": "admin",
    "member_count": 12,
    "security_ready": false,
    "active_epoch_number": null
  }
}
```

Direct items return `group: null`. Do not create plaintext last-message previews.

## Files

```text
apps/group_chat/models.py
apps/group_chat/permissions.py
apps/group_chat/selectors.py
apps/group_chat/migrations/00xx_group_audit_event.py
apps/group_chat/tests/test_group_permissions.py
apps/group_chat/tests/test_group_audit.py
apps/chat_messages/access_selectors.py
apps/chat_messages/serializers.py
apps/chat_messages/services.py
apps/chat_messages/tests/test_room_list_group_items.py
```

## Tests

Audit every security mutation, verify generic authorization failures, verify active-member room visibility, and rerun all direct send/history tests.

## Frontend

Use a discriminated union:

```ts
type RoomListItem = DirectRoomListItem | GroupRoomListItem;
```

Add direct and group room-list components. Join Identity profile/contact data in the frontend view-model layer.


---

# 12. Phase 5 — Group encryption epochs

## Goal

Create cryptographic membership epochs. Group sending remains disabled until sender keys and distributions exist.

## Model

Add `GroupEncryptionEpoch`:

```text
GroupEncryptionEpoch
- id: UUID
- group_room: FK Room
- epoch_number: positive integer
- status: active | closed
- rotation_reason
- created_by_user_id
- membership_snapshot_hash
- created_at
- closed_at
```

Constraints:

- unique `(group_room, epoch_number)`;
- only one active epoch per group;
- monotonic epoch numbers;
- closed epoch cannot reactivate;
- no epoch for direct rooms.

`membership_snapshot_hash` is a hash of canonical active member IDs plus membership versions. It is not a secret.

## Initial epoch

After this phase:

- new groups create epoch 1 in the same transaction as group creation;
- existing active group rooms receive epoch 1 through a data migration or management command;
- direct rooms remain unchanged.

## APIs

```http
GET  /api/v1/groups/{group_id}/epochs/current/
GET  /api/v1/groups/{group_id}/epochs/
POST /api/v1/groups/{group_id}/epochs/rotate/
```

Manual rotation request:

```json
{
  "reason": "security_incident"
}
```

Only owner/admin can manually rotate.

## Rotation transaction

1. lock group room;
2. lock current active epoch;
3. recompute membership snapshot;
4. close current epoch;
5. create next epoch;
6. revoke old sender-key registrations when Phase 6 exists;
7. write audit event;
8. commit.

## Files

```text
apps/group_chat/models.py
apps/group_chat/serializers/epochs.py
apps/group_chat/services/epochs.py
apps/group_chat/views/epochs.py
apps/group_chat/selectors.py
apps/group_chat/urls.py
apps/group_chat/migrations/00xx_group_encryption_epoch.py
apps/group_chat/tests/test_epoch_api.py
```

## Tests

Test epoch 1 creation, direct-room exclusion, one-active constraint, role rules, concurrent rotation, monotonic numbering, snapshot changes, closed immutability and audit events.

## Frontend

```text
src/messenger/
├── api/group-keys.api.ts
├── storage/group-epoch.repository.ts
├── services/groups/group-epoch.service.ts
├── hooks/groups/useGroupSecurityState.ts
└── ui/groups/GroupSecurityStatus.tsx
```

Frontend states:

```text
not_initialized
epoch_active_sender_key_missing
key_distribution_pending
ready
rotation_required
```

Composer remains disabled until `ready`.

---

# 13. Phase 6 — Sender-key registration

## Goal

Let each active member device register public sender-key metadata for the current epoch.

## Client responsibility

For `(group, epoch, sender device)` the client creates:

- random sender-chain secret;
- signing keypair;
- sender key ID;
- local chain iteration.

Only public metadata is uploaded.

## Model

```text
GroupSenderKey
- id: UUID
- group_room
- epoch
- sender_user_id
- sender_device
- sender_key_id: UUID
- signing_public_key
- key_algorithm
- signing_algorithm
- key_version
- highest_accepted_iteration
- is_active
- created_at
- revoked_at
```

Constraints:

- device belongs to sender;
- sender is active member;
- epoch belongs to group;
- unique sender key ID;
- one active key per sender device per epoch;
- no private sender-chain or signing key field.

## APIs

```http
POST   /api/v1/groups/{group_id}/sender-keys/register/
GET    /api/v1/groups/{group_id}/sender-keys/mine/?device_id={uuid}
DELETE /api/v1/groups/{group_id}/sender-keys/{sender_key_id}/
```

Register request:

```json
{
  "sender_device_id": "uuid",
  "epoch_number": 2,
  "sender_key_id": "uuid",
  "signing_public_key": "base64",
  "key_algorithm": "group-sender-key-v1",
  "signing_algorithm": "ed25519",
  "key_version": 1
}
```

Exact retry returns existing registration with `200`. Changed retry returns `409`.

## Files

```text
apps/group_chat/models.py
apps/group_chat/serializers/sender_keys.py
apps/group_chat/services/sender_keys.py
apps/group_chat/views/sender_keys.py
apps/group_chat/urls.py
apps/group_chat/migrations/00xx_group_sender_key.py
apps/group_chat/tests/test_sender_key_api.py
```

## Tests

Cover authentication, ownership, active membership, current epoch, inactive device, exact retry, changed retry, uniqueness, multi-device user support, removal and secret-field absence.

## Frontend

```text
src/messenger/
├── crypto/group/sender-key.ts
├── crypto/group/sender-key-codec.ts
├── crypto/group/sender-key-signature.ts
├── storage/group-key.repository.ts
├── services/groups/group-sender-key.service.ts
├── hooks/groups/useGroupSenderKey.ts
└── ui/groups/GroupKeySetupProgress.tsx
```

Local secret state must be encrypted before IndexedDB persistence and never placed in Redux, Zustand devtools, localStorage, logs or analytics.

---

# 14. Phase 7 — Device roster and sender-key distribution

## Goal

Distribute each sender key to every authorized active member device through existing pairwise E2EE sessions.

## Model

```text
GroupSenderKeyDistribution
- id: UUID
- sender_key
- recipient_user_id
- recipient_device
- encrypted_sender_key
- distribution_metadata
- distribution_version
- status: pending | stored | acknowledged
- created_at
- acknowledged_at
```

Unique `(sender_key, recipient_device)`.

## Device roster API

```http
GET /api/v1/groups/{group_id}/devices/?epoch_number={n}
```

Return public records for active member devices only, including membership version/snapshot data. Never return private keys, inactive devices, removed-member devices or recovery private bundles.

## Distribution APIs

```http
POST /api/v1/groups/{group_id}/sender-keys/{sender_key_id}/distributions/
GET  /api/v1/groups/{group_id}/sender-keys/{sender_key_id}/pending/
GET  /api/v1/groups/{group_id}/sender-key-distributions/inbox/?device_id={uuid}
POST /api/v1/groups/{group_id}/sender-key-distributions/acknowledge/
```

Batch request:

```json
{
  "epoch_number": 2,
  "distributions": [
    {
      "recipient_user_id": "2",
      "recipient_device_id": "uuid",
      "encrypted_sender_key": "base64",
      "distribution_metadata": {
        "algorithm": "double-ratchet",
        "session_reference": "opaque",
        "message_number": 17,
        "nonce": "base64"
      },
      "distribution_version": 1
    }
  ]
}
```

## Completeness policy

A sender key is send-ready when every required active member device has a stored distribution. Acknowledgement improves visibility but does not block forever.

Required set includes:

- all active devices of all active members;
- sender user's other devices;
- sender device may be omitted because it owns the local secret.

## Transaction

1. lock sender key;
2. confirm current epoch;
3. recompute required devices;
4. validate supplied recipients;
5. reject removed/unexpected devices;
6. store exact retries idempotently;
7. reject changed retries;
8. commit atomically.

## Files

```text
apps/group_chat/models.py
apps/group_chat/serializers/sender_keys.py
apps/group_chat/services/distributions.py
apps/group_chat/views/sender_keys.py
apps/group_chat/selectors.py
apps/group_chat/migrations/00xx_group_sender_key_distribution.py
apps/group_chat/tests/test_sender_key_distribution_api.py
```

## Tests

Test roster filtering, ownership, missing/unexpected recipients, exact/changed retry, atomic rollback, device-specific inbox, acknowledgement, stale epoch, snapshot race and direct-prekey regression.

## Frontend

```text
src/messenger/
├── services/groups/group-device-roster.service.ts
├── services/groups/group-key-distribution.service.ts
├── crypto/group/sender-key-distribution.ts
├── hooks/groups/useGroupKeyDistribution.ts
└── ui/groups/GroupKeyDistributionProgress.tsx
```

Coordinator:

1. fetch epoch;
2. ensure local sender key;
3. fetch roster;
4. ensure pairwise sessions;
5. encrypt per-device distributions;
6. upload batches;
7. check pending count;
8. mark sender ready.

---

# 15. Phase 8 — Encrypted group message send

## Goal

Add a dedicated group-send API using sender-key encryption.

## Model

Add `GroupMessageEncryption` in `apps/chat_messages/models.py`:

```text
GroupMessageEncryption
- id: UUID
- message: one-to-one Message
- group_room
- epoch
- sender_key
- chain_iteration
- signature
- encryption_metadata
- created_at
```

Constraints:

- message room equals group room;
- message sender/device matches sender key owner/device;
- epoch and key belong to group;
- unique `(sender_key, chain_iteration)`;
- nonnegative iteration.

Do not use `MessageKeyEnvelope` for normal group sender-key messages.

## API

```http
POST /api/v1/messages/group/
```

Request:

```json
{
  "group_id": "uuid",
  "sender_device_id": "uuid",
  "client_message_id": "uuid",
  "epoch_number": 2,
  "sender_key_id": "uuid",
  "chain_iteration": 42,
  "message_type": "text",
  "encrypted_payload": "base64-ciphertext",
  "encryption_metadata": {
    "algorithm": "group-sender-key-v1",
    "nonce": "base64",
    "content_encoding": "myna-message-v1"
  },
  "signature": "base64-signature",
  "reply_to_message_id": null,
  "client_sent_at": "2026-06-27T00:00:00Z"
}
```

## Validation order

1. authenticate;
2. validate shape and limits;
3. active membership and send policy;
4. active owned device;
5. current epoch lock;
6. active sender-key lock;
7. complete distribution coverage;
8. idempotency lookup;
9. monotonic chain iteration;
10. reply target same group;
11. create `Message`;
12. create `GroupMessageEncryption`;
13. advance highest iteration;
14. commit.

## Response

New request returns `201` and `message_created: true`. Exact retry returns `200` and `message_created: false`. Changed retry returns `409`.

## Files

```text
apps/chat_messages/models.py
apps/chat_messages/group_serializers.py
apps/chat_messages/group_services.py
apps/chat_messages/group_views.py
apps/chat_messages/urls.py
apps/chat_messages/migrations/00xx_group_message_encryption.py
apps/chat_messages/tests/test_group_message_api.py
```

## Tests

Cover membership, admin-only-send policy, device/key/epoch ownership, complete distributions, iteration replay/concurrency, exact/changed retry, reply target, direct-send regression and ciphertext opacity.

## Frontend

```text
src/messenger/
├── api/group-messages.api.ts
├── crypto/group/group-message-cipher.ts
├── services/groups/group-message.service.ts
├── hooks/groups/useSendGroupMessage.ts
└── ui/groups/GroupConversationView.tsx
```

Send transaction:

1. lock local sender state;
2. allocate iteration;
3. derive message key;
4. encrypt canonical plaintext;
5. sign ciphertext and associated data;
6. persist encrypted outbox request and next local state atomically;
7. POST;
8. reconcile by `client_message_id`.

After uncertainty, retry the exact stored request. Never reuse an iteration with different ciphertext.

---

# 16. Phase 9 — Group encrypted history

## Goal

Return authorized group ciphertext and public sender metadata for local decryption.

## API

```http
GET /api/v1/messages/groups/{group_id}/history/?device_id={uuid}&page_size=50&cursor={cursor}
```

Use cursor ordering `-created_at, -id`, default 50, maximum 100.

## Authorization window

The requesting user owns the active device and sees only messages inside authorized membership windows.

Default policy:

```text
join_history_visible = false
```

Eligibility:

```text
message.created_at >= membership.joined_at
and
message.created_at < left_at/removed_at when present
```

Reactivation begins a new membership version/window.

## History item

```json
{
  "id": "uuid",
  "room_id": "uuid",
  "sender_user_id": "2",
  "sender_device_id": "uuid",
  "client_message_id": "uuid",
  "message_type": "text",
  "encrypted_payload": "base64",
  "encryption_metadata": {
    "algorithm": "group-sender-key-v1",
    "nonce": "base64"
  },
  "epoch_number": 2,
  "sender_key_id": "uuid",
  "chain_iteration": 42,
  "signature": "base64",
  "signing_public_key": "base64",
  "reply_to_id": null,
  "created_at": "iso"
}
```

Do not include all device distributions in history. The client fetches its distribution inbox separately.

## Files

```text
apps/chat_messages/group_history_serializers.py
apps/chat_messages/group_history_services.py
apps/chat_messages/group_history_views.py
apps/chat_messages/access_selectors.py
apps/chat_messages/urls.py
apps/chat_messages/tests/test_group_history_api.py
```

## Tests

Test owned device, active/former membership windows, before-join and after-removal exclusion, other-group isolation, pagination stability, public signing key, no secret/distribution leakage and direct-history regression.

## Frontend

```text
src/messenger/
├── services/groups/group-history.service.ts
├── services/groups/group-key-inbox.service.ts
├── hooks/groups/useGroupHistory.ts
├── hooks/groups/useGroupKeyInbox.ts
└── ui/groups/GroupMessageList.tsx
```

Receive flow:

1. fetch history;
2. identify missing sender keys;
3. fetch device inbox;
4. decrypt/store sender keys locally;
5. verify signature;
6. derive chain message key;
7. decrypt message.

---

# 17. Phase 10 — Automatic epoch rotation and device synchronization

## Goal

Make membership/device changes automatically invalidate future access.

## Rotation triggers

- member added;
- member removed;
- member leaves;
- ban/unban/reactivation;
- active member device added;
- active member device deactivated;
- manual security rotation.

## Explicit orchestration

Do not put core security in implicit Django model signals.

Membership example:

```python
with transaction.atomic():
    remove_member(...)
    rotate_group_epoch(...)
```

Device registration/deactivation uses `transaction.on_commit()` plus a durable transition queue.

## Model

```text
GroupSecurityTransition
- id
- group_room
- reason
- actor_user_id
- target_user_id
- target_device_id
- status: pending | applied | failed
- attempt_count
- last_error_code
- created_at
- applied_at
```

## Key behavior

On rotation:

- old epoch closes;
- old sender keys become inactive;
- old distributions remain for historical decryption;
- new messages require new sender keys;
- removed member receives no new roster/distribution;
- UI blocks composer until ready.

## Files

```text
apps/group_chat/models.py
apps/group_chat/services/memberships.py
apps/group_chat/services/epochs.py
apps/group_chat/services/security_transitions.py
apps/group_chat/migrations/00xx_group_security_transition.py
apps/group_chat/tests/test_membership_epoch_rotation.py
apps/group_chat/tests/test_device_epoch_rotation.py
apps/e2ee_devices/group_device_hooks.py
apps/e2ee_devices/services.py
apps/e2ee_devices/tests/test_group_device_hooks.py
```

## Tests

Test each trigger, direct-only device registration, old-key invalidation, historical decryption preservation, removed-user isolation, transition retry, concurrent member change/send and direct-send regression.

## Frontend

```text
src/messenger/
├── services/groups/group-security-coordinator.service.ts
├── hooks/groups/useGroupSecurityCoordinator.ts
├── ui/groups/GroupRotationBanner.tsx
└── ui/groups/GroupSecurityBlockedComposer.tsx
```

On epoch change, stop old sends, archive old local key, create/register/distribute new key, then resume.


---

# 18. Phase 11 — Group cloud recovery

## Goal

Extend the existing recovery architecture to group messages without weakening direct recovery.

## Initial design

Create one `MessageRecoveryEnvelope` per eligible recovery-enabled group user per group message.

The sender client:

1. derives the group message key from its sender chain;
2. encrypts the message once;
3. wraps the same message key with each eligible member's recovery public key;
4. submits group ciphertext and recovery envelopes atomically.

The server never receives the plaintext message key.

## Recovery recipients API

```http
GET /api/v1/groups/{group_id}/recovery-recipients/
```

Response:

```json
{
  "success": true,
  "message": "Group recovery recipients retrieved successfully.",
  "data": {
    "group_id": "uuid",
    "epoch_number": 4,
    "recipients": [
      {
        "user_id": "1",
        "recovery_public_key": "base64",
        "recovery_version": 2
      }
    ]
  }
}
```

This group-authorized endpoint is safer than resolving an arbitrary large list of user IDs.

## Group-send extension

`POST /api/v1/messages/group/` gains:

```json
{
  "recovery_envelopes": [
    {
      "recovery_owner_user_id": "1",
      "recovery_key_version": 2,
      "wrapped_message_key": "base64",
      "key_wrap_metadata": {
        "algorithm": "recovery-box-v1",
        "nonce": "base64"
      },
      "envelope_version": 1
    }
  ]
}
```

Server validates:

- expected owners are authorized current-epoch members with active recovery;
- exactly one envelope per expected owner;
- no removed/nonmember owner;
- current recovery version;
- exact retry equality;
- message and envelopes commit atomically.

## Existing recovery API reuse

These existing APIs should support authorized direct and group messages:

```http
GET  /api/v1/messages/recovery-history/
POST /api/v1/messages/recovery/rewrap/
GET  /api/v1/messages/recovery/backfill/candidates/
POST /api/v1/messages/recovery/backfill/
GET  /api/v1/messages/recovery/coverage/
POST /api/v1/e2ee/recovery/rotate/
DELETE /api/v1/e2ee/recovery/
```

Required selector updates:

- recovery history returns group messages when the user owns an envelope;
- group backfill respects membership windows and selected-device authorization;
- coverage counts direct and group messages;
- rotation updates all owner envelopes;
- deletion removes only that user's direct/group recovery envelopes.

## Files

```text
apps/group_chat/selectors.py
apps/group_chat/views/sender_keys.py
apps/group_chat/urls.py
apps/group_chat/tests/test_group_recovery_recipients_api.py

apps/chat_messages/group_recovery_serializers.py
apps/chat_messages/group_recovery_services.py
apps/chat_messages/group_services.py
apps/chat_messages/recovery_services.py
apps/chat_messages/recovery_backfill_services.py
apps/chat_messages/recovery_coverage_services.py
apps/chat_messages/access_selectors.py
apps/chat_messages/tests/test_group_recovery_api.py
```

## Tests

Cover authorized recipients, omitted users without recovery, removed-member exclusion, missing/unexpected envelopes, stale versions, exact/changed retries, group recovery history, cross-user isolation, backfill, coverage, rotation across direct/group and recovery deletion.

## Frontend

```text
src/messenger/
├── services/groups/group-recovery.service.ts
├── services/groups/group-recovery-backfill.service.ts
├── hooks/groups/useGroupRecoveryRecipients.ts
├── hooks/groups/useGroupRecoveryCoverage.ts
└── ui/recovery/GroupRecoveryCoverageSection.tsx
```

Send coordinator fetches recipient recovery versions, wraps the same group message key, and includes envelopes in the same idempotent request.

---

# 19. Phase 12 — Receipts, encrypted attachments and encrypted message events

## Goal

Complete practical group-message behavior while keeping content E2EE.

## Receipt model

Add common `MessageReceipt`:

```text
MessageReceipt
- id
- message
- recipient_user_id
- recipient_device: optional
- delivered_at
- read_at
- created_at
- updated_at
```

Use device-level delivery records and aggregate them for user-level UI.

## Receipt APIs

```http
POST /api/v1/messages/receipts/delivered/
POST /api/v1/messages/receipts/read/
GET  /api/v1/messages/{message_id}/receipts/
```

Batch delivered request:

```json
{
  "device_id": "uuid",
  "message_ids": ["uuid-1", "uuid-2"]
}
```

Read-through request:

```json
{
  "device_id": "uuid",
  "group_id": "uuid",
  "read_through_message_id": "uuid"
}
```

Rules:

- only authorized messages;
- timestamps move forward only;
- exact retry idempotent;
- historical member may acknowledge previously authorized messages but not newer ones.

## Encrypted attachments

Add `EncryptedAttachment`:

```text
EncryptedAttachment
- id
- uploader_user_id
- uploader_device
- storage_provider
- storage_key
- ciphertext_sha256
- ciphertext_size
- media_category
- upload_status
- created_at
- completed_at
- expires_at: optional
```

Never store plaintext attachment key. The client encrypts before upload.

APIs:

```http
POST   /api/v1/messages/attachments/initiate/
POST   /api/v1/messages/attachments/{attachment_id}/complete/
GET    /api/v1/messages/attachments/{attachment_id}/download/
DELETE /api/v1/messages/attachments/{attachment_id}/
```

Original filename, exact MIME and attachment key should live inside encrypted message plaintext when privacy requires it.

## Edits, deletes, reactions and system events

Represent them as encrypted event messages through existing direct/group send paths.

Message types:

```text
edit
delete
reaction
system
```

Example encrypted plaintext:

```json
{
  "event": "message.reaction",
  "target_message_id": "uuid",
  "reaction": "👍",
  "operation": "add"
}
```

The server validates structural target references and room authorization but does not inspect secret content.

## Files

```text
apps/chat_messages/models.py
apps/chat_messages/receipt_serializers.py
apps/chat_messages/receipt_services.py
apps/chat_messages/receipt_views.py
apps/chat_messages/attachment_serializers.py
apps/chat_messages/attachment_services.py
apps/chat_messages/attachment_views.py
apps/chat_messages/group_services.py
apps/chat_messages/services.py
apps/chat_messages/urls.py
apps/chat_messages/migrations/00xx_message_receipt.py
apps/chat_messages/migrations/00xy_encrypted_attachment.py
apps/chat_messages/tests/test_group_receipts_api.py
apps/chat_messages/tests/test_encrypted_attachments_api.py
apps/chat_messages/tests/test_encrypted_message_events.py
```

## Tests

Receipts: ownership, authorization, batch validation, idempotency, monotonicity and aggregates. Attachments: limits, hash, completion, authorization, historical boundaries, expiry and no plaintext key fields. Events: same-room targets, sender policy, epoch rules and idempotency.

## Frontend

```text
src/messenger/
├── api/receipts.api.ts
├── api/attachments.api.ts
├── services/receipt.service.ts
├── services/encrypted-attachment.service.ts
├── services/groups/group-message-event.service.ts
├── crypto/attachments/attachment-cipher.ts
├── crypto/attachments/attachment-hash.ts
├── hooks/useMessageReceipts.ts
├── hooks/useEncryptedAttachmentUpload.ts
└── ui/
    ├── messages/ReceiptSummary.tsx
    ├── composer/AttachmentPicker.tsx
    └── groups/GroupMessageActionMenu.tsx
```

---

# 20. Phase 13 — Django Channels, Redis and realtime delivery

## Goal

Add instant delivery after all REST flows are stable. REST remains authoritative.

## Dependencies

Pin project-compatible versions of:

```text
channels
channels-redis
daphne or another supported ASGI server
Redis client dependencies
```

## Backend structure

```text
messenger_config/
├── settings.py
├── asgi.py
└── urls.py

apps/realtime/
├── __init__.py
├── apps.py
├── authentication.py
├── consumers.py
├── events.py
├── publishers.py
├── routing.py
├── serializers.py
├── services.py
├── views.py
├── urls.py
└── tests/
    ├── test_ticket_api.py
    ├── test_consumer_auth.py
    ├── test_group_events.py
    └── test_reconnect_reconciliation.py
```

## WebSocket ticket

Do not place a long-lived access JWT in a query string.

```http
POST /api/v1/realtime/tickets/
```

Request:

```json
{
  "device_id": "uuid"
}
```

Response:

```json
{
  "success": true,
  "message": "Realtime ticket created successfully.",
  "data": {
    "ticket": "single-use-short-lived-token",
    "expires_at": "iso"
  }
}
```

Ticket is one-use, short-lived and bound to user/device.

## Socket

```text
wss://<messenger-host>/ws/messenger/?ticket=<ticket>
```

Use one device-specific socket rather than one socket per room.

## Events

```text
connection.accepted
message.stored
group.message.stored
group.epoch.changed
group.sender_key.registered
group.sender_key.distribution.available
group.member.added
group.member.removed
group.metadata.updated
message.delivered
message.read
typing.started
typing.stopped
presence.changed
reconciliation.required
```

Recommended minimal message event:

```json
{
  "type": "group.message.stored",
  "event_id": "uuid",
  "group_id": "uuid",
  "message_id": "uuid",
  "client_message_id": "uuid",
  "created_at": "iso"
}
```

Recipient fetches authoritative data through REST.

## Publish after commit

Use `transaction.on_commit()` or a durable outbox. Never broadcast a message that later rolls back.

Recommended outbox:

```text
RealtimeOutboxEvent
- id
- event_type
- audience
- payload
- status
- attempts
- created_at
- published_at
```

## Reconnect sequence

1. obtain ticket;
2. connect socket;
3. refresh room list;
4. fetch group security state;
5. fetch sender-key inbox;
6. fetch history newer than local cursor/time;
7. reconcile outbox by `client_message_id`.

## Tests

Test ticket expiry/one-use/device ownership, consumer auth, active audience, removed-member exclusion, commit-before-publish, duplicate event IDs, reconnect, Redis outage persistence and typing limits.

## Frontend

```text
src/messenger/
├── api/realtime.api.ts
├── realtime/messenger-socket.ts
├── realtime/event-types.ts
├── realtime/event-router.ts
├── realtime/reconnect-policy.ts
├── realtime/reconciliation.service.ts
├── state/realtime.store.ts
├── hooks/useMessengerSocket.ts
└── services/groups/group-realtime.service.ts
```

Rule:

```text
WebSocket event = hint
REST response/history = authority
```

---

# 21. Phase 14 — Security hardening, load tests, deployment and documentation

## Goal

Make the complete group system production-ready.

## Rate limits

Apply per-user/per-device limits to group creation, membership changes, rotations, key registration, distributions, send, receipts, attachments, realtime tickets and typing.

## Payload limits

Set maximums for:

- group metadata;
- members per mutation and group total;
- distribution batch size;
- encrypted message payload;
- recovery envelope count;
- attachment ciphertext size;
- receipt batch size;
- WebSocket frame size.

## Index review

Consider indexes for:

```text
RoomMember(room_id, user_id, is_active)
RoomMember(user_id, is_active)
GroupEncryptionEpoch(group_room_id, status)
GroupSenderKey(group_room_id, epoch_id, sender_device_id, is_active)
GroupSenderKeyDistribution(recipient_device_id, status)
GroupMessageEncryption(group_room_id, created_at)
GroupMessageEncryption(sender_key_id, chain_iteration)
Message(room_id, created_at, id)
MessageRecoveryEnvelope(recovery_owner_user_id, recovery_key_version)
MessageReceipt(message_id, recipient_user_id)
RealtimeOutboxEvent(status, created_at)
```

Verify actual query plans and MySQL/PostgreSQL portability.

## Security tests

Test replayed distributions, replayed iterations, forged IDs, stale epoch/member races, concurrent limits, cross-group references, malformed/oversized metadata, generic errors, secret logging prevention, audit sanitization and ticket replay.

## Load tests

Use representative groups:

```text
small: 5 members
medium: 50 members
large initial limit: 256 members
```

Measure roster, distributions, send transaction, history, recovery validation, receipts and realtime fan-out.

## Operational jobs

```text
retry_group_security_transitions
expire_unused_attachments
publish_realtime_outbox
prune_expired_realtime_tickets
audit_group_epoch_consistency
audit_sender_key_distribution_coverage
```

## Deployment

Local:

- MySQL;
- local Redis;
- ASGI server.

Production:

- Neon PostgreSQL;
- managed Redis compatible with Channels;
- ASGI deployment;
- encrypted object storage;
- TLS/WSS only.

## Final documents

Update:

```text
documentation.md
MYNA_MESSENGER_API_FRONTEND_E2EE_SPEC_UPDATED.md
MYNA_GROUP_CHAT_BACKEND_IMPLEMENTATION_ROADMAP.md
```

Also provide Postman/OpenAPI contracts, environment variables, WebSocket events, recovery flows and frontend TypeScript types.

---

# 22. Final backend folder tree

```text
messenger/
├── manage.py
├── requirements.txt
├── messenger_config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   ├── wsgi.py
│   ├── authentication.py
│   └── identity_client.py
└── apps/
    ├── rooms/
    │   ├── models.py
    │   ├── selectors.py
    │   ├── migrations/
    │   └── tests/
    ├── e2ee_devices/
    │   ├── existing direct and recovery files
    │   ├── group_device_hooks.py
    │   ├── migrations/
    │   └── tests/
    ├── group_chat/
    │   ├── apps.py
    │   ├── constants.py
    │   ├── models.py
    │   ├── permissions.py
    │   ├── selectors.py
    │   ├── urls.py
    │   ├── serializers/
    │   │   ├── groups.py
    │   │   ├── memberships.py
    │   │   ├── epochs.py
    │   │   └── sender_keys.py
    │   ├── services/
    │   │   ├── groups.py
    │   │   ├── memberships.py
    │   │   ├── epochs.py
    │   │   ├── sender_keys.py
    │   │   ├── distributions.py
    │   │   └── security_transitions.py
    │   ├── views/
    │   │   ├── groups.py
    │   │   ├── memberships.py
    │   │   ├── epochs.py
    │   │   └── sender_keys.py
    │   ├── migrations/
    │   └── tests/
    ├── chat_messages/
    │   ├── existing direct and recovery files
    │   ├── access_selectors.py
    │   ├── group_serializers.py
    │   ├── group_services.py
    │   ├── group_views.py
    │   ├── group_history_serializers.py
    │   ├── group_history_services.py
    │   ├── group_history_views.py
    │   ├── group_recovery_serializers.py
    │   ├── group_recovery_services.py
    │   ├── receipt_serializers.py
    │   ├── receipt_services.py
    │   ├── receipt_views.py
    │   ├── attachment_serializers.py
    │   ├── attachment_services.py
    │   ├── attachment_views.py
    │   ├── migrations/
    │   └── tests/
    └── realtime/
        ├── apps.py
        ├── authentication.py
        ├── consumers.py
        ├── events.py
        ├── publishers.py
        ├── routing.py
        ├── serializers.py
        ├── services.py
        ├── views.py
        ├── urls.py
        └── tests/
```

---

# 23. Final frontend folder tree

```text
src/messenger/
├── api/
│   ├── messenger-client.ts
│   ├── device.api.ts
│   ├── prekey.api.ts
│   ├── rooms.api.ts
│   ├── messages.api.ts
│   ├── recovery.api.ts
│   ├── groups.api.ts
│   ├── group-keys.api.ts
│   ├── group-messages.api.ts
│   ├── receipts.api.ts
│   ├── attachments.api.ts
│   └── realtime.api.ts
├── crypto/
│   ├── crypto.worker.ts
│   ├── crypto-worker-client.ts
│   ├── direct/
│   ├── group/
│   │   ├── sender-key.ts
│   │   ├── sender-key-codec.ts
│   │   ├── sender-key-distribution.ts
│   │   ├── sender-key-signature.ts
│   │   ├── group-message-cipher.ts
│   │   └── group-protocol-types.ts
│   ├── attachments/
│   │   ├── attachment-cipher.ts
│   │   └── attachment-hash.ts
│   └── codecs/
├── storage/
│   ├── device.repository.ts
│   ├── ratchet.repository.ts
│   ├── outbox.repository.ts
│   ├── recovery.repository.ts
│   ├── group-key.repository.ts
│   └── group-epoch.repository.ts
├── services/
│   ├── existing direct/recovery services
│   ├── receipt.service.ts
│   ├── encrypted-attachment.service.ts
│   └── groups/
│       ├── group-room.service.ts
│       ├── group-membership.service.ts
│       ├── group-epoch.service.ts
│       ├── group-device-roster.service.ts
│       ├── group-sender-key.service.ts
│       ├── group-key-distribution.service.ts
│       ├── group-message.service.ts
│       ├── group-history.service.ts
│       ├── group-key-inbox.service.ts
│       ├── group-security-coordinator.service.ts
│       ├── group-recovery.service.ts
│       └── group-recovery-backfill.service.ts
├── realtime/
│   ├── messenger-socket.ts
│   ├── event-types.ts
│   ├── event-router.ts
│   ├── reconnect-policy.ts
│   └── reconciliation.service.ts
├── state/
│   ├── room.store.ts
│   ├── message.store.ts
│   ├── outbox.store.ts
│   ├── recovery.store.ts
│   ├── group.store.ts
│   └── realtime.store.ts
├── hooks/
│   ├── existing direct/recovery hooks
│   ├── useMessageReceipts.ts
│   ├── useEncryptedAttachmentUpload.ts
│   ├── useMessengerSocket.ts
│   └── groups/
│       ├── useGroups.ts
│       ├── useCreateGroup.ts
│       ├── useGroupDetail.ts
│       ├── useGroupMembers.ts
│       ├── useManageGroupMembers.ts
│       ├── useGroupSecurityState.ts
│       ├── useGroupSenderKey.ts
│       ├── useGroupKeyDistribution.ts
│       ├── useSendGroupMessage.ts
│       ├── useGroupHistory.ts
│       ├── useGroupKeyInbox.ts
│       └── useGroupRecoveryCoverage.ts
└── ui/
    ├── conversations/
    ├── composer/
    ├── messages/
    ├── recovery/
    └── groups/
        ├── CreateGroupDialog.tsx
        ├── GroupInfoPanel.tsx
        ├── GroupMembersPanel.tsx
        ├── AddGroupMembersDialog.tsx
        ├── MemberRoleMenu.tsx
        ├── TransferOwnershipDialog.tsx
        ├── LeaveGroupDialog.tsx
        ├── GroupSecurityStatus.tsx
        ├── GroupKeySetupProgress.tsx
        ├── GroupKeyDistributionProgress.tsx
        ├── GroupConversationView.tsx
        ├── GroupMessageList.tsx
        ├── GroupRotationBanner.tsx
        └── GroupSecurityBlockedComposer.tsx
```


---

# 24. Final group API index

## Group metadata and membership

```http
POST   /api/v1/groups/
GET    /api/v1/groups/
GET    /api/v1/groups/{group_id}/
PATCH  /api/v1/groups/{group_id}/

GET    /api/v1/groups/{group_id}/members/
POST   /api/v1/groups/{group_id}/members/
DELETE /api/v1/groups/{group_id}/members/{user_id}/
PATCH  /api/v1/groups/{group_id}/members/{user_id}/role/
POST   /api/v1/groups/{group_id}/members/{user_id}/ban/
POST   /api/v1/groups/{group_id}/members/{user_id}/unban/
POST   /api/v1/groups/{group_id}/leave/
POST   /api/v1/groups/{group_id}/transfer-ownership/
```

## Epochs and sender keys

```http
GET    /api/v1/groups/{group_id}/epochs/current/
GET    /api/v1/groups/{group_id}/epochs/
POST   /api/v1/groups/{group_id}/epochs/rotate/

POST   /api/v1/groups/{group_id}/sender-keys/register/
GET    /api/v1/groups/{group_id}/sender-keys/mine/
DELETE /api/v1/groups/{group_id}/sender-keys/{sender_key_id}/

GET    /api/v1/groups/{group_id}/devices/
POST   /api/v1/groups/{group_id}/sender-keys/{sender_key_id}/distributions/
GET    /api/v1/groups/{group_id}/sender-keys/{sender_key_id}/pending/
GET    /api/v1/groups/{group_id}/sender-key-distributions/inbox/
POST   /api/v1/groups/{group_id}/sender-key-distributions/acknowledge/
```

## Messages and history

```http
POST /api/v1/messages/group/
GET  /api/v1/messages/groups/{group_id}/history/
```

## Recovery

```http
GET /api/v1/groups/{group_id}/recovery-recipients/
```

Existing generic recovery endpoints continue to serve authorized direct and group messages.

## Receipts and attachments

```http
POST   /api/v1/messages/receipts/delivered/
POST   /api/v1/messages/receipts/read/
GET    /api/v1/messages/{message_id}/receipts/

POST   /api/v1/messages/attachments/initiate/
POST   /api/v1/messages/attachments/{attachment_id}/complete/
GET    /api/v1/messages/attachments/{attachment_id}/download/
DELETE /api/v1/messages/attachments/{attachment_id}/
```

## Realtime

```http
POST /api/v1/realtime/tickets/
```

```text
WSS /ws/messenger/?ticket=<single-use-ticket>
```

---

# 25. Direct-chat synchronization checklist

Run after every phase.

## Rooms

- Direct rooms still use `direct_pair_key`.
- Group rooms never use `direct_pair_key`.
- Direct first-send room creation remains automatic.
- Group creation remains explicit.
- Room-list output stays backward compatible.

## Messages

- Direct send still requires per-device envelopes.
- Group send uses sender keys and no normal per-device message envelopes.
- Both store ciphertext in `Message`.
- Both use `client_message_id` idempotency.
- Group fields live in `GroupMessageEncryption`.

## Devices

- Existing registration remains authoritative.
- Group keys reference existing active devices.
- Group roster never creates devices.
- Device deactivation triggers group rotation but does not alter direct-history rules.

## Recovery

- `MessageRecoveryEnvelope` stays generic.
- Direct send keeps direct participant rules.
- Group send uses epoch membership rules.
- Recovery history returns only owner envelopes.
- Rotation/deletion operate across direct and group owner envelopes.

## Frontend

- One sidebar handles `direct | group`.
- Direct crypto remains pairwise Double Ratchet.
- Group crypto remains sender-key based.
- Shared UI renders decrypted canonical messages.
- Private key state stays outside UI stores.

---

# 26. Testing strategy

## Model tests

Validate constraints, lifecycle, uniqueness and direct compatibility.

## Service tests

Validate transactions, locks, idempotency, authorization, rotation and distribution completeness.

## API tests

Validate authentication, status codes, response envelopes, pagination, generic errors and sensitive-data absence.

## Concurrency tests

Validate iteration replay, ownership transfer, group size, simultaneous removal/send and simultaneous rotation.

## Frontend unit tests

Validate API adapters, room unions, worker calls, local key repositories, outbox retry and reconciliation.

## Frontend integration tests

Validate create group, add members, initialize/distribute keys, send/decrypt, remove member, rotate, recover and reconnect.

## Never mock away security decisions

Mocks may replace Identity or object storage, but tests must still assert exact user/device IDs, active states, epochs, versions and idempotent equality.

## Migration checks

```powershell
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py migrate
```

Test against a clone of an existing direct-chat database, not only an empty database.

## Full test commands

```powershell
python manage.py check

python manage.py test apps.group_chat.tests -v 2
python manage.py test apps.chat_messages.tests -v 2
python manage.py test apps.e2ee_devices.tests -v 2
python manage.py test apps.realtime.tests -v 2

python manage.py test `
  apps.rooms.tests `
  apps.e2ee_devices.tests `
  apps.group_chat.tests `
  apps.chat_messages.tests `
  apps.realtime.tests `
  -v 2
```

A complete implementation may reach roughly 300–400 tests. Test quality is more important than an exact count.

---

# 27. Frontend end-to-end workflows

## Create group

```text
Select Identity/contact users
        ↓
POST /groups/
        ↓
Fetch detail/members/current epoch
        ↓
Generate sender key locally
        ↓
Register public sender-key metadata
        ↓
Fetch member device roster
        ↓
Create pairwise encrypted distributions
        ↓
Upload distributions
        ↓
Enable composer
```

## Send group message

```text
Check epoch and readiness
        ↓
Lock local sender-key state
        ↓
Derive next message key
        ↓
Encrypt canonical plaintext
        ↓
Sign ciphertext + associated data
        ↓
Resolve group recovery recipients
        ↓
Wrap key for recovery-enabled members
        ↓
Persist exact encrypted outbox request
        ↓
POST /messages/group/
        ↓
Reconcile message ID
```

## Receive group message

```text
WebSocket hint or REST refresh
        ↓
Fetch encrypted history
        ↓
Ensure sender key exists locally
        ↓
Fetch device distribution inbox if missing
        ↓
Decrypt distribution through pairwise session
        ↓
Verify sender signature
        ↓
Derive message key
        ↓
Decrypt canonical message
        ↓
Send receipts
```

## Remove member

```text
Admin removes member
        ↓
Backend closes old epoch
        ↓
Backend creates new epoch
        ↓
Clients receive epoch.changed
        ↓
Remaining devices stop old sender keys
        ↓
Generate/distribute new keys
        ↓
Resume send
```

## New device

```text
Register device
        ↓
Affected groups rotate epoch
        ↓
New device gets current distributions
        ↓
Old history is not automatically granted
        ↓
Recovery may restore authorized old messages
```

## Recovery

```text
Unlock recovery private key locally
        ↓
GET recovery history
        ↓
Unwrap group message keys
        ↓
Decrypt independently of live sender chain
        ↓
Rewrap to new device where required
        ↓
Backfill missing recovery from trusted old device
```

---

# 28. Security acceptance criteria

The implementation is incomplete unless all are true:

- server never receives plaintext group message;
- server never receives plaintext attachment;
- server never stores sender-chain secret;
- server never stores sender signing private key;
- distributions are device-specific ciphertext;
- removed member receives no new epoch key;
- stale epoch send is rejected;
- chain iteration cannot be reused;
- exact retry is safe;
- changed retry conflicts;
- history respects membership windows;
- recovery owner was authorized for the message;
- another user's recovery envelope is never exposed;
- direct chat remains green;
- WebSocket cannot grant authorization;
- REST reconciles missed events;
- audit logs contain no secrets;
- oversized payloads are rejected;
- production uses TLS/WSS.

---

# 29. Codex rules

Codex must not:

- create a new group microservice;
- replace direct Double Ratchet with group sender keys;
- use direct device envelopes for every group message;
- store sender-key secrets in Django;
- store private keys in Redux/Zustand/localStorage;
- derive recovery from account password;
- allow ownerless active groups;
- allow multiple active epochs;
- let removed users receive new distributions;
- publish WebSocket events before commit;
- use WebSocket as persistence;
- mutate an idempotent request after network failure;
- skip full regression tests;
- hard-code migration numbers;
- assume Identity profiles live in Messenger;
- expose enumeration through detailed errors.

Codex should:

- preserve current naming where practical;
- keep views thin;
- use serializers for validation;
- use services for transactions;
- use selectors for reads;
- use type-safe frontend adapters;
- isolate crypto in workers/services;
- update documentation for approved design changes.

---

# 30. Definition of complete group chat

Complete means:

1. group CRUD works;
2. roles and ownership are enforced;
3. every group has an epoch;
4. every sender device has an independent sender key;
5. keys are distributed through pairwise E2EE;
6. messages are encrypted once and stored as ciphertext;
7. membership/device changes rotate epochs;
8. removed members cannot decrypt future messages;
9. authorized devices can decrypt history;
10. group messages participate in recovery;
11. receipts work;
12. attachments are encrypted before upload;
13. reactions/edits/deletes are encrypted events;
14. WebSockets provide instant hints;
15. REST reconciles missed events;
16. direct chat remains functional;
17. MySQL/PostgreSQL migrations pass;
18. security/concurrency/load tests pass;
19. frontend private keys remain isolated;
20. docs match deployed behavior.

---

# 31. Recommended commit sequence

```text
group/phase-01-scaffold
group/phase-02-group-crud
group/phase-03-memberships
group/phase-04-permissions-room-sync
group/phase-05-epochs
group/phase-06-sender-key-registration
group/phase-07-key-distribution
group/phase-08-group-send
group/phase-09-group-history
group/phase-10-automatic-rotation
group/phase-11-group-recovery
group/phase-12-receipts-attachments-events
group/phase-13-realtime
group/phase-14-hardening
```

At each boundary run targeted tests and the full Messenger suite before continuing.

---

# 32. Final note

Group E2EE is not only a new REST endpoint. It is a coordinated system involving membership authorization, epochs, device-specific sender-key distribution, ciphertext persistence, recovery, multi-device state and realtime reconciliation.

Following these phases in order protects the already working direct-chat backend while allowing Myna to become a complete encrypted group-messaging system.
