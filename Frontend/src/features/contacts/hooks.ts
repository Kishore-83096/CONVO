import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addContact,
  deleteContact,
  getContactDetail,
  getContacts,
  renameContact,
  searchContactByNumber,
  updateContactBlock,
  updateContactGhost,
  type UpdateContactBlockPayload,
  type UpdateContactGhostPayload,
} from "./api";
import type {
  AddContactFormValues,
  ContactSearchFormValues,
  RenameContactFormValues,
} from "./schemas";

export const contactQueryKeys = {
  all: ["contacts"] as const,
  list: () => [...contactQueryKeys.all, "list"] as const,
  detail: (contactId: string) =>
    [...contactQueryKeys.all, "detail", contactId] as const,
};

export function useSearchContact() {
  return useMutation({
    mutationFn: (values: ContactSearchFormValues) => searchContactByNumber(values),
  });
}

export function useAddContact() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (values: AddContactFormValues) => addContact(values),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: contactQueryKeys.list() });
    },
  });
}

export function useContacts() {
  return useQuery({
    queryKey: contactQueryKeys.list(),
    queryFn: getContacts,
  });
}

export function useContactDetail(contactId: string) {
  return useQuery({
    enabled: contactId.trim().length > 0,
    queryKey: contactQueryKeys.detail(contactId),
    queryFn: () => getContactDetail(contactId),
  });
}

export function useRenameContact() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      contactId,
      values,
    }: {
      contactId: string;
      values: RenameContactFormValues;
    }) => renameContact(contactId, values),
    onSuccess: async (_result, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: contactQueryKeys.list() }),
        queryClient.invalidateQueries({
          queryKey: contactQueryKeys.detail(variables.contactId),
        }),
      ]);
    },
  });
}

export function useUpdateContactBlock() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      contactId,
      values,
    }: {
      contactId: string;
      values: UpdateContactBlockPayload;
    }) => updateContactBlock(contactId, values),
    onSuccess: async (_result, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: contactQueryKeys.list() }),
        queryClient.invalidateQueries({
          queryKey: contactQueryKeys.detail(variables.contactId),
        }),
      ]);
    },
  });
}

export function useUpdateContactGhost() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      contactId,
      values,
    }: {
      contactId: string;
      values: UpdateContactGhostPayload;
    }) => updateContactGhost(contactId, values),
    onSuccess: async (_result, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: contactQueryKeys.list() }),
        queryClient.invalidateQueries({
          queryKey: contactQueryKeys.detail(variables.contactId),
        }),
      ]);
    },
  });
}

export function useDeleteContact() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ contactId }: { contactId: string }) => deleteContact(contactId),
    onSuccess: async (_result, variables) => {
      queryClient.removeQueries({
        queryKey: contactQueryKeys.detail(variables.contactId),
      });

      await queryClient.invalidateQueries({ queryKey: contactQueryKeys.list() });
    },
  });
}