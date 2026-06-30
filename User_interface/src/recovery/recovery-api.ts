import messengerClient from "@/api/messenger-client";
import { request } from "@/api/http-client";

import type {
  ApiEnvelope,
  JsonObject,
} from "@/api/api-types";

export type RecoveryUnlockMethod =
  | "recovery_key"
  | "webauthn_prf"
  | "recovery_key_and_webauthn_prf";

export type RecoveryBundleEncryptionMetadata = {
  algorithm: "xchacha20poly1305-ietf";
  nonce: string;
  unlock_method: RecoveryUnlockMethod;
  [key: string]: unknown;
};

export type RecoveryKeyWrapMetadata = {
  algorithm: "recovery-box-v1";
  nonce: string;
  [key: string]: unknown;
};

export type DeviceSyncWrapMetadata = {
  algorithm: "device-sync-v1";
  nonce: string;
  [key: string]: unknown;
};

export type RecoverySetupRequest = {
  recovery_public_key: string;
  encrypted_recovery_private_key: string;
  encryption_metadata: RecoveryBundleEncryptionMetadata;
};

export type RecoveryStatusResult = {
  configured: boolean;
  is_active: boolean;
  recovery_version: number | null;
  created_at: string | null;
  updated_at: string | null;
  rotated_at: string | null;
  disabled_at: string | null;
};

export type RecoveryBundleResult = {
  recovery_public_key: string;
  encrypted_recovery_private_key: string;
  encryption_metadata: RecoveryBundleEncryptionMetadata;
  recovery_version: number;
  is_active: true;
  created_at: string;
  updated_at: string;
  rotated_at: string | null;
};

export type RecoveryPublicKeysRequest = {
  user_ids: string[];
};

export type RecoveryPublicKeysResult = {
  public_keys: Array<{
    user_id: string;
    recovery_public_key: string;
    recovery_version: number;
    updated_at: string;
  }>;
};

export type RecoveryHistoryResult = {
  next: string | null;
  previous: string | null;
  messages: JsonObject[];
};

export type RecoveryRewrapRequest = {
  device_id: string;
  envelopes: Array<{
    message_id: string;
    wrapped_message_key: string;
    key_wrap_metadata: DeviceSyncWrapMetadata;
    envelope_version: number;
  }>;
};

export type RecoveryBackfillCandidatesResult = {
  device_id: string;
  recovery_key_version: number;
  next: string | null;
  previous: string | null;
  messages: JsonObject[];
};

export type RecoveryBackfillRequest = {
  device_id: string;
  recovery_key_version: number;
  envelopes: Array<{
    message_id: string;
    wrapped_message_key: string;
    key_wrap_metadata: RecoveryKeyWrapMetadata;
    envelope_version: number;
  }>;
};

export type RecoveryCoverageResult = {
  recovery_version: number;
  total_eligible_messages: number;
  current_version_covered_messages: number;
  missing_recovery_envelopes: number;
  stale_recovery_envelopes: number;
  coverage_percent: number;
  is_complete: boolean;
  active_devices: Array<{
    device_id: string;
    device_name: string;
    platform: string;
    backfill_candidate_count: number;
  }>;
};

export type RecoveryRotateRequest = RecoverySetupRequest & {
  current_recovery_version: number;
  recovery_envelopes: Array<{
    message_id: string;
    wrapped_message_key: string;
    key_wrap_metadata: RecoveryKeyWrapMetadata;
    envelope_version: number;
  }>;
};

export type DisableRecoveryResult = {
  bundle_deleted: boolean;
  deleted_recovery_envelope_count: number;
};

export const recoveryApi = {
  setup(payload: RecoverySetupRequest) {
    return request<ApiEnvelope<RecoveryStatusResult>>(
      messengerClient,
      {
        method: "POST",
        url: "/e2ee/recovery/setup/",
        data: payload,
      },
    );
  },

  status() {
    return request<ApiEnvelope<RecoveryStatusResult>>(
      messengerClient,
      {
        method: "GET",
        url: "/e2ee/recovery/status/",
      },
    );
  },

  bundle() {
    return request<ApiEnvelope<RecoveryBundleResult>>(
      messengerClient,
      {
        method: "GET",
        url: "/e2ee/recovery/bundle/",
      },
    );
  },

  resolvePublicKeys(payload: RecoveryPublicKeysRequest) {
    return request<ApiEnvelope<RecoveryPublicKeysResult>>(
      messengerClient,
      {
        method: "POST",
        url: "/e2ee/recovery/public-keys/resolve/",
        data: payload,
      },
    );
  },

  rotate(payload: RecoveryRotateRequest) {
    return request<ApiEnvelope<JsonObject>>(
      messengerClient,
      {
        method: "POST",
        url: "/e2ee/recovery/rotate/",
        data: payload,
      },
    );
  },

  disable() {
    return request<ApiEnvelope<DisableRecoveryResult>>(
      messengerClient,
      {
        method: "DELETE",
        url: "/e2ee/recovery/",
      },
    );
  },

  history() {
    return request<ApiEnvelope<RecoveryHistoryResult>>(
      messengerClient,
      {
        method: "GET",
        url: "/messages/recovery-history/",
      },
    );
  },

  rewrap(payload: RecoveryRewrapRequest) {
    return request<ApiEnvelope<JsonObject>>(
      messengerClient,
      {
        method: "POST",
        url: "/messages/recovery/rewrap/",
        data: payload,
      },
    );
  },

  backfillCandidates(deviceId: string) {
    return request<ApiEnvelope<RecoveryBackfillCandidatesResult>>(
      messengerClient,
      {
        method: "GET",
        url: "/messages/recovery/backfill/candidates/",
        params: {
          device_id: deviceId,
        },
      },
    );
  },

  backfill(payload: RecoveryBackfillRequest) {
    return request<ApiEnvelope<JsonObject>>(
      messengerClient,
      {
        method: "POST",
        url: "/messages/recovery/backfill/",
        data: payload,
      },
    );
  },

  coverage() {
    return request<ApiEnvelope<RecoveryCoverageResult>>(
      messengerClient,
      {
        method: "GET",
        url: "/messages/recovery/coverage/",
      },
    );
  },
};
