import { useState } from "react";
import {
  RefreshCw,
  Search,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui";

import { ContactDetailDrawer } from "./ContactDetailDrawer";
import { ContactSearch } from "./ContactSearch";
import { ContactCard } from "./ContactPreviewCard";
import { SaveContactDialog } from "./SaveContactDialog";
import { useContacts } from "./use-contacts";

import type {
  ContactSummary,
  SearchContactResponse,
} from "./contacts-types";

export function ContactsPage() {
  const {
    list,
    selectedContactId,
    selectContact,
    openDetailDrawer,
    closeDetailDrawer,
    detailDrawerOpen,
  } = useContacts();

  const [searchResult, setSearchResult] =
    useState<SearchContactResponse | null>(null);

  const [dialogOpen, setDialogOpen] =
    useState(false);

  const contactsQuery = useQuery({
    queryKey: ["contacts", "list"],
    queryFn: list,
  });

  const contacts = contactsQuery.data ?? [];

  function handleSearchSuccess(
    result: SearchContactResponse,
  ) {
    setSearchResult(result);
  }

  function handleSaveContact() {
    setDialogOpen(true);
  }

  function handleCloseDialog() {
    setDialogOpen(false);
  }

  function handleSaveSuccess() {
    setDialogOpen(false);

    setSearchResult(null);

    void contactsQuery.refetch();
  }

  function handleOpenContact(contact: ContactSummary) {
    selectContact(contact.id);
    openDetailDrawer();
  }

  function handleCloseDetail() {
    closeDetailDrawer();
    selectContact(null);
  }

  return (
    <section className="workspace-view active">
      <header className="workspace-header">
        <div className="workspace-title-row">
          <div>
            <span className="section-kicker">Contacts</span>
            <h1>Contacts</h1>
          </div>

          <Button
            type="button"
            variant="secondary"
            leftIcon={<RefreshCw size={16} />}
            loading={contactsQuery.isFetching}
            onClick={() => {
              void contactsQuery.refetch();
            }}
          >
            Refresh
          </Button>
        </div>
      </header>

      <div className="workspace-content">
        <div className="contacts-layout">
          <section className="contacts-panel">
            <div className="contacts-panel__header">
              <Search size={18} aria-hidden="true" />
              <div>
                <h2>Find a contact</h2>
                <p>Search by contact number and save the result.</p>
              </div>
            </div>

            <ContactSearch
              onSearchSuccess={handleSearchSuccess}
            />

            {searchResult && (
              <div className="contacts-page__result">
                <ContactCard
                  contact={searchResult}
                  onAddContact={handleSaveContact}
                />
              </div>
            )}
          </section>

          <section className="contacts-panel contacts-panel--list">
            <div className="contacts-panel__header">
              <div>
                <h2>Saved contacts</h2>
                <p>{contacts.length} saved contact{contacts.length === 1 ? "" : "s"}</p>
              </div>
            </div>

            {contactsQuery.isLoading && (
              <p className="sidebar-state">Loading contacts...</p>
            )}

            {contactsQuery.isError && (
              <div className="contacts-error">
                {contactsQuery.error instanceof Error
                  ? contactsQuery.error.message
                  : "Unable to load contacts."}
              </div>
            )}

            {!contactsQuery.isLoading && contacts.length === 0 && (
              <p className="sidebar-state">No saved contacts yet.</p>
            )}

            {contacts.length > 0 && (
              <div className="contacts-list">
                {contacts.map((contact) => (
                  <button
                    key={contact.id}
                    type="button"
                    className="contacts-list-item"
                    onClick={() => handleOpenContact(contact)}
                  >
                    <ContactAvatar
                      name={contact.saved_name}
                      imageUrl={contact.profile_picture?.url}
                    />

                    <span>{contact.saved_name}</span>
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>

      <SaveContactDialog
        open={dialogOpen}
        contact={searchResult}
        onClose={handleCloseDialog}
        onSuccess={handleSaveSuccess}
      />

      <ContactDetailDrawer
        open={detailDrawerOpen}
        contactId={selectedContactId}
        onClose={handleCloseDetail}
      />
    </section>
  );
}

function ContactAvatar({
  name,
  imageUrl,
}: {
  name: string;
  imageUrl?: string;
}) {
  return (
    <span className="contacts-avatar">
      {imageUrl ? (
        <img src={imageUrl} alt="" />
      ) : (
        name.charAt(0).toUpperCase()
      )}
    </span>
  );
}
