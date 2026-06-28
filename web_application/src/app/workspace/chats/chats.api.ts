import type { ProfilePicture } from "@/app/identity/contacts/contacts.types"

export interface ChatSummary {
  id: string
  roomId: string
  roomType: "direct" | "group"
  name: string
  status: string
  lastMessage: string
  time: string
  memberUserIds: string[]
  recipientUserId: string | null
  contactId: number | null
  profilePicture: ProfilePicture | null
  lastMessageAt: string | null
}
