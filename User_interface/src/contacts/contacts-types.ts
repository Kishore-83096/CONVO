// ============================================================
// Contact Avatar
// ============================================================

export interface ContactAvatar {
  url: string;
  format: string;
  width: number;
  height: number;
  bytes: number;
  created_at: string;
  updated_at: string;
}

// ============================================================
// Contact Models
// ============================================================

export interface ContactSummary {
  id: number;

  saved_name: string;

  contact_number: number;

  username: string;

  full_name: string;

  profile_picture: ContactAvatar | null;
}

export interface ContactDetail
  extends ContactSummary {
  delivery_policy?: DeliveryPolicy;
}

// ============================================================
// Delivery Policy
// ============================================================

export interface DeliveryPolicy {
  owner_user_id: number;

  target_user_id: number;

  is_blocked: boolean;

  blocked_at: string | null;

  is_ghosted: boolean;

  ghost_until: string | null;

  ghost_permanent: boolean;

  ghost_duration_option:
    | "1h"
    | "6h"
    | "12h"
    | "24h"
    | "permanent"
    | null;

  policy_version: number;

  updated_at: string;
}

// ============================================================
// Search Contact
// ============================================================

export interface SearchContactRequest {
  contact_number: number;
}

export interface SearchContactResponse {
  contact_number: number;
  full_name: string;
  username: string;
  profile_picture: ContactAvatar | null;
}

// ============================================================
// Add Contact
// ============================================================

export interface AddContactRequest {
  contact_number: number;
  saved_name: string;
}

// ============================================================
// Rename Contact
// ============================================================

export interface RenameContactRequest {
  saved_name: string;
}

// ============================================================
// Block Contact
// ============================================================

export interface BlockContactRequest {
  is_blocked: boolean;
}

// ============================================================
// Ghost Contact
// ============================================================

export interface GhostContactRequest {
  is_ghosted: boolean;

  duration?:
    | "1h"
    | "6h"
    | "12h"
    | "24h"
    | "permanent";
}

// ============================================================
// Resolve Recipient
// ============================================================

export interface ResolveRecipientRequest {
  contact_id: number;
}

export interface ResolveRecipientResponse {
  contact_id: number;

  contact_user_id: string;

  saved_name: string;

  contact_number: string;
}

// ============================================================
// Collections
// ============================================================

export type ContactsList =
  ContactSummary[];