import { contactsService } from "./contacts-service";
import { useContactsStore } from "./contacts-store";

export function useContacts() {
  const selectedContactId = useContactsStore(
    (state) => state.selectedContactId,
  );

  const searchQuery = useContactsStore(
    (state) => state.searchQuery,
  );

  const filter = useContactsStore(
    (state) => state.filter,
  );

  const detailDrawerOpen = useContactsStore(
    (state) => state.detailDrawerOpen,
  );

  return {
    // UI State
    selectedContactId,
    searchQuery,
    filter,
    detailDrawerOpen,

    // UI Actions
    selectContact:
      useContactsStore.getState().selectContact,

    setSearchQuery:
      useContactsStore.getState().setSearchQuery,

    setFilter:
      useContactsStore.getState().setFilter,

    openDetailDrawer:
      useContactsStore.getState().openDetailDrawer,

    closeDetailDrawer:
      useContactsStore.getState().closeDetailDrawer,

    reset:
      useContactsStore.getState().reset,

    // Service Methods
    search: contactsService.search.bind(
      contactsService,
    ),

    add: contactsService.add.bind(
      contactsService,
    ),

    list: contactsService.list.bind(
      contactsService,
    ),

    detail: contactsService.detail.bind(
      contactsService,
    ),

    rename: contactsService.rename.bind(
      contactsService,
    ),

    block: contactsService.block.bind(
      contactsService,
    ),

    ghost: contactsService.ghost.bind(
      contactsService,
    ),

    remove: contactsService.remove.bind(
      contactsService,
    ),

    resolveRecipient:
      contactsService.resolveRecipient.bind(
        contactsService,
      ),
  };
}