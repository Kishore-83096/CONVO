import { create } from "zustand";

interface ContactsStore {
  /**
   * Currently selected contact.
   */
  selectedContactId: number | null;

  /**
   * Current search text.
   */
  searchQuery: string;

  /**
   * Contact list filter.
   */
  filter:
    | "all"
    | "blocked"
    | "ghosted";

  /**
   * Contact detail drawer state.
   */
  detailDrawerOpen: boolean;

  /**
   * Select a contact.
   */
  selectContact(
    contactId: number | null,
  ): void;

  /**
   * Update search query.
   */
  setSearchQuery(
    query: string,
  ): void;

  /**
   * Update filter.
   */
  setFilter(
    filter:
      | "all"
      | "blocked"
      | "ghosted",
  ): void;

  /**
   * Open detail drawer.
   */
  openDetailDrawer(): void;

  /**
   * Close detail drawer.
   */
  closeDetailDrawer(): void;

  /**
   * Reset UI state.
   */
  reset(): void;
}

export const useContactsStore =
  create<ContactsStore>((set) => ({
    selectedContactId: null,

    searchQuery: "",

    filter: "all",

    detailDrawerOpen: false,

    selectContact: (
      selectedContactId,
    ) =>
      set({
        selectedContactId,
      }),

    setSearchQuery: (
      searchQuery,
    ) =>
      set({
        searchQuery,
      }),

    setFilter: (filter) =>
      set({
        filter,
      }),

    openDetailDrawer: () =>
      set({
        detailDrawerOpen: true,
      }),

    closeDetailDrawer: () =>
      set({
        detailDrawerOpen: false,
      }),

    reset: () =>
      set({
        selectedContactId: null,
        searchQuery: "",
        filter: "all",
        detailDrawerOpen: false,
      }),
  }));