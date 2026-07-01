import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createMyProfileAddress,
  createMyProfileBasic,
  createMyProfileEvent,
  createMyProfilePicture,
  deleteMyProfileAddress,
  deleteMyProfileBasic,
  deleteMyProfileEvent,
  deleteMyProfilePicture,
  getMyProfile,
  getMyProfileAddress,
  getMyProfileBasic,
  getMyProfileEvent,
  getMyProfileEvents,
  getMyProfilePicture,
  updateMyProfileAddress,
  updateMyProfileBasic,
  updateMyProfileEvent,
  updateMyProfilePicture,
} from "./api";

export const profileQueryKeys = {
  all: ["profiles"] as const,
  me: () => [...profileQueryKeys.all, "me"] as const,
  basic: () => [...profileQueryKeys.all, "me", "basic"] as const,
  address: () => [...profileQueryKeys.all, "me", "address"] as const,
  events: () => [...profileQueryKeys.all, "me", "events"] as const,
  event: (eventId: string) =>
    [...profileQueryKeys.all, "me", "events", eventId] as const,
  picture: () => [...profileQueryKeys.all, "me", "picture"] as const,
};

export function useMyProfile() {
  return useQuery({
    queryKey: profileQueryKeys.me(),
    queryFn: getMyProfile,
  });
}

export function useMyProfileBasic() {
  return useQuery({
    queryKey: profileQueryKeys.basic(),
    queryFn: getMyProfileBasic,
  });
}

export function useCreateMyProfileBasic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createMyProfileBasic,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.me() }),
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.basic() }),
      ]);
    },
  });
}

export function useUpdateMyProfileBasic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateMyProfileBasic,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.me() }),
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.basic() }),
      ]);
    },
  });
}

export function useDeleteMyProfileBasic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteMyProfileBasic,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.me() }),
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.basic() }),
      ]);
    },
  });
}

export function useMyProfileAddress() {
  return useQuery({
    queryKey: profileQueryKeys.address(),
    queryFn: getMyProfileAddress,
  });
}

export function useCreateMyProfileAddress() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createMyProfileAddress,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.me() }),
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.address() }),
      ]);
    },
  });
}

export function useUpdateMyProfileAddress() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateMyProfileAddress,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.me() }),
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.address() }),
      ]);
    },
  });
}

export function useDeleteMyProfileAddress() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteMyProfileAddress,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.me() }),
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.address() }),
      ]);
    },
  });
}

export function useMyProfileEvents() {
  return useQuery({
    queryKey: profileQueryKeys.events(),
    queryFn: getMyProfileEvents,
  });
}

export function useCreateMyProfileEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createMyProfileEvent,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.me() }),
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.events() }),
      ]);
    },
  });
}

export function useMyProfileEvent(eventId: string) {
  return useQuery({
    enabled: eventId.trim().length > 0,
    queryKey: profileQueryKeys.event(eventId),
    queryFn: () => getMyProfileEvent(eventId),
  });
}

export function useUpdateMyProfileEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateMyProfileEvent,
    onSuccess: async (_result, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.me() }),
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.events() }),
        queryClient.invalidateQueries({
          queryKey: profileQueryKeys.event(variables.eventId),
        }),
      ]);
    },
  });
}

export function useDeleteMyProfileEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteMyProfileEvent,
    onSuccess: async (_result, eventId) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.me() }),
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.events() }),
        queryClient.invalidateQueries({
          queryKey: profileQueryKeys.event(eventId),
        }),
      ]);
    },
  });
}

export function useMyProfilePicture(enabled = true) {
  return useQuery({
    enabled,
    queryKey: profileQueryKeys.picture(),
    queryFn: getMyProfilePicture,
  });
}

export function useCreateMyProfilePicture() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createMyProfilePicture,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.me() }),
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.picture() }),
      ]);
    },
  });
}

export function useUpdateMyProfilePicture() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateMyProfilePicture,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.me() }),
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.picture() }),
      ]);
    },
  });
}

export function useDeleteMyProfilePicture() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteMyProfilePicture,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.me() }),
        queryClient.invalidateQueries({ queryKey: profileQueryKeys.picture() }),
      ]);
    },
  });
}
