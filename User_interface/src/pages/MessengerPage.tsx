import { MessageCircle } from "lucide-react";

import { BrandLogo } from "@/components/brand";

export function MessengerPage() {
  return (
    <section className="main-view active" id="emptyMainView">
      <div className="empty-main-content">
        <BrandLogo className="empty-brand" iconClassName="empty-main-icon" />
        <h1>Messages</h1>
        <p>Select a conversation when messages are available.</p>
        <div className="empty-main-action">
          <MessageCircle aria-hidden="true" />
          <span>MYNA workspace</span>
        </div>
      </div>
    </section>
  );
}
