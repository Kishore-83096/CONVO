import { useState } from "react";

import { ContactSearch } from "./ContactSearch";
import { ContactCard } from "./ContactPreviewCard";
import { SaveContactDialog } from "./SaveContactDialog";

import type { SearchContactResponse } from "./contacts-types";

export function ContactsPage() {
  const [searchResult, setSearchResult] =
    useState<SearchContactResponse | null>(null);

  const [dialogOpen, setDialogOpen] =
    useState(false);

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
  }

  return (
    <section className="contacts-page">
      <div className="contacts-page__search">
        <ContactSearch
          onSearchSuccess={handleSearchSuccess}
        />
      </div>

      {searchResult && (
        <div
          className="contacts-page__result"
          style={{
            marginTop: "var(--spacing-xl)",
          }}
        >
          <ContactCard
            contact={searchResult}
            onAddContact={handleSaveContact}
          />
        </div>
      )}

      <SaveContactDialog
        open={dialogOpen}
        contact={searchResult}
        onClose={handleCloseDialog}
        onSuccess={handleSaveSuccess}
      />
    </section>
  );
}