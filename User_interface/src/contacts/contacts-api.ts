import identityClient from "@/api/identity-client";
import { request } from "@/api/http-client";

import type { ApiEnvelope } from "@/api/api-types";

import type {
  AddContactRequest,
  ContactDetail,
  ContactSummary,
  GhostContactRequest,
  RenameContactRequest,
  ResolveRecipientRequest,
  ResolveRecipientResponse,
  SearchContactRequest,
  SearchContactResponse,
  BlockContactRequest,
} from "./contacts-types";

export const contactsApi = {
  /**
   * Search a user by contact number.
   */
  search(payload: SearchContactRequest) {
    return request<ApiEnvelope<SearchContactResponse>>(
      identityClient,
      {
        method: "POST",
        url: "/contacts/search",
        data: payload,
      },
    );
  },

  /**
   * Save a new contact.
   */
  add(payload: AddContactRequest) {
    return request<ApiEnvelope<ContactSummary>>(
      identityClient,
      {
        method: "POST",
        url: "/contacts",
        data: payload,
      },
    );
  },

  /**
   * Fetch all saved contacts.
   */
  list() {
    return request<ApiEnvelope<ContactSummary[]>>(
      identityClient,
      {
        method: "GET",
        url: "/contacts",
      },
    );
  },

  /**
   * Fetch a single contact.
   */
  detail(contactId: number) {
    return request<ApiEnvelope<ContactDetail>>(
      identityClient,
      {
        method: "GET",
        url: `/contacts/${contactId}`,
      },
    );
  },

  /**
   * Rename a saved contact.
   */
  rename(
    contactId: number,
    payload: RenameContactRequest,
  ) {
    return request<ApiEnvelope<ContactSummary>>(
      identityClient,
      {
        method: "PATCH",
        url: `/contacts/${contactId}`,
        data: payload,
      },
    );
  },

  /**
   * Block or unblock a contact.
   */
  block(
    contactId: number,
    payload: BlockContactRequest,
  ) {
    return request<ApiEnvelope<ContactDetail>>(
      identityClient,
      {
        method: "PATCH",
        url: `/contacts/${contactId}/block`,
        data: payload,
      },
    );
  },

  /**
   * Ghost or unghost a contact.
   */
  ghost(
    contactId: number,
    payload: GhostContactRequest,
  ) {
    return request<ApiEnvelope<ContactDetail>>(
      identityClient,
      {
        method: "PATCH",
        url: `/contacts/${contactId}/ghost`,
        data: payload,
      },
    );
  },

  /**
   * Delete a saved contact.
   */
  remove(contactId: number) {
    return request<ApiEnvelope<null>>(
      identityClient,
      {
        method: "DELETE",
        url: `/contacts/${contactId}`,
      },
    );
  },

  /**
   * Resolve recipient user ID before
   * starting an encrypted conversation.
   */
  resolveRecipient(
    payload: ResolveRecipientRequest,
  ) {
    return request<
      ApiEnvelope<ResolveRecipientResponse>
    >(identityClient, {
      method: "POST",
      url: "/contacts/resolve-message-recipient",
      data: payload,
    });
  },
};