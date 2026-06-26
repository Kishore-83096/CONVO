export interface ChatSummary {
  id: string
  name: string
  status: string
  lastMessage: string
  time: string
  unreadCount?: number
}

export const demoChats: ChatSummary[] = [
  {
    id: "arun-kumar",
    name: "Arun Kumar",
    status: "Online",
    lastMessage: "Okay, I will send it today.",
    time: "10:42 AM",
    unreadCount: 2,
  },
  {
    id: "priya-sharma",
    name: "Priya Sharma",
    status: "Last seen recently",
    lastMessage: "Thank you for the update.",
    time: "10:15 AM",
  },
  {
    id: "myna-team",
    name: "Myna Team",
    status: "4 members online",
    lastMessage: "New project discussion",
    time: "9:46 AM",
    unreadCount: 5,
  },
  {
    id: "meena-das",
    name: "Meena Das",
    status: "Offline",
    lastMessage: "The document looks good.",
    time: "Yesterday",
  },
]
