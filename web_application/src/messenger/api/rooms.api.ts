import {
  MessengerApiError,
  messengerRequest,
} from "./messenger-client"

import type {
  RoomListItem,
  RoomListResponse,
} from "./messenger-api.types"

export async function listMessengerRooms(
  accessToken: string,
): Promise<RoomListResponse> {
  try {
    return await messengerRequest<RoomListItem[]>(
      "/rooms/",
      {},
      accessToken,
    )
  } catch (error) {
    if (
      error instanceof MessengerApiError
      && error.status === 404
    ) {
      return messengerRequest<RoomListItem[]>(
        "/messages/rooms/",
        {},
        accessToken,
      )
    }

    throw error
  }
}
