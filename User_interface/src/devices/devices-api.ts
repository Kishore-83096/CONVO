import messengerClient from "@/api/messenger-client";
import { request } from "@/api/http-client";

import type {
  ApiEnvelope,
  JsonObject,
} from "@/api/api-types";

export type DevicePlatform =
  | "web"
  | "android"
  | "ios"
  | "desktop"
  | string;

export type DevicePublicRecord = {
  id: string;
  user_id: string;
  device_name: string;
  platform: DevicePlatform;
  registration_id: number;
  identity_key_public: string;
  signed_prekey_id: number;
  signed_prekey_public: string;
  signed_prekey_signature: string;
  key_algorithm: string;
  key_bundle_version: number;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
  last_seen_at?: string | null;
};

export type RegisterDeviceRequest = {
  device_name: string;
  platform: DevicePlatform;
  registration_id: number;
  identity_key_public: string;
  signed_prekey_id: number;
  signed_prekey_public: string;
  signed_prekey_signature: string;
  key_algorithm: string;
  key_bundle_version: number;
};

export type OneTimePreKeyUploadItem = {
  key_id: number;
  public_key: string;
};

export type UploadOneTimePreKeysRequest = {
  prekeys: OneTimePreKeyUploadItem[];
};

export type UploadPreKeysResult = {
  uploaded_count?: number;
  available_count?: number;
  prekeys_created?: number;
  prekeys_unchanged?: number;
  device_id?: string;
};

export type ClaimPreKeyBundlesRequest = {
  recipient_user_id: string;
};

export type ClaimedDevicePreKeyBundle = {
  device_id: string;
  user_id: string;
  registration_id: number;
  identity_key_public: string;
  signed_prekey_id: number;
  signed_prekey_public: string;
  signed_prekey_signature: string;
  key_algorithm: string;
  key_bundle_version: number;
  one_time_prekey: {
    key_id: number;
    public_key: string;
  } | null;
};

export type ClaimPreKeyBundlesResult = {
  bundles: ClaimedDevicePreKeyBundle[];
};

export type WhoAmIResult = JsonObject;

export const devicesApi = {
  whoami() {
    return request<WhoAmIResult>(
      messengerClient,
      {
        method: "GET",
        url: "/auth/whoami/",
      },
    );
  },

  registerDevice(payload: RegisterDeviceRequest) {
    return request<ApiEnvelope<DevicePublicRecord | { device: DevicePublicRecord }>>(
      messengerClient,
      {
        method: "POST",
        url: "/e2ee/devices/register/",
        data: payload,
      },
    );
  },

  uploadPreKeys(
    deviceId: string,
    payload: UploadOneTimePreKeysRequest,
  ) {
    return request<ApiEnvelope<UploadPreKeysResult>>(
      messengerClient,
      {
        method: "POST",
        url: `/e2ee/devices/${encodeURIComponent(deviceId)}/prekeys/`,
        data: payload,
      },
    );
  },

  claimPreKeyBundles(payload: ClaimPreKeyBundlesRequest) {
    return request<ApiEnvelope<ClaimPreKeyBundlesResult>>(
      messengerClient,
      {
        method: "POST",
        url: "/e2ee/prekey-bundles/claim/",
        data: payload,
      },
    );
  },
};

export function normalizeRegisteredDevice(
  value: DevicePublicRecord | { device: DevicePublicRecord } | undefined,
): DevicePublicRecord | undefined {
  if (!value) {
    return undefined;
  }

  return "device" in value ? value.device : value;
}
