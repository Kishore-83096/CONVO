import { Button } from "@/components/ui";

import type {
  SearchContactResponse,
} from "./contacts-types";

interface ContactCardProps {
  contact: SearchContactResponse;

  onAddContact(): void;

  loading?: boolean;
}

export function ContactCard({
  contact,
  onAddContact,
  loading = false,
}: ContactCardProps) {
  return (
    <div className="contact-card">
      <div className="contact-card__header">
        <div className="contact-card__avatar">
          {contact.profile_picture?.url ? (
            <img
              src={contact.profile_picture.url}
              alt={contact.full_name}
            />
          ) : (
            <span>
              {contact.full_name
                .charAt(0)
                .toUpperCase()}
            </span>
          )}
        </div>

        <div className="contact-card__info">
          <h3>
            {contact.full_name}
          </h3>

          <p>
            @{contact.username}
          </p>
        </div>
      </div>

      <div
        style={{
          marginTop:
            "var(--spacing-lg)",
        }}
      >
        <Button
          fullWidth
          loading={loading}
          onClick={onAddContact}
        >
          Save Contact
        </Button>
      </div>
    </div>
  );
}