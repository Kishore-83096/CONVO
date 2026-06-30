import { createBrowserRouter } from "react-router-dom";

import { AppShell, PublicLayout } from "@/components/layout";
import { RequireAuth } from "@/auth/RequireAuth";

import { LandingPage } from "@/pages/LandingPage";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { RedirectIfAuthenticated } from "@/auth/RedirectIfAuthenticated";
import { MessengerPage } from "@/pages/MessengerPage";
import { ContactsPage } from "@/pages/ContactsPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { SettingsPage } from "@/pages/SettingsPage";

export const router = createBrowserRouter([
  // ---------------------------------------
  // Public Routes
  // ---------------------------------------
  {
  element: <PublicLayout />,
  children: [
    {
      element: <RedirectIfAuthenticated />,
      children: [
        {
          path: "/",
          element: <LandingPage />,
        },
        {
          path: "/login",
          element: <LoginPage />,
        },
        {
          path: "/register",
          element: <RegisterPage />,
        },
      ],
    },
  ],
},

  // ---------------------------------------
  // Protected Routes
  // ---------------------------------------
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          {
            path: "/app",
            element: <MessengerPage />,
          },
          {
            path: "/contacts",
            element: <ContactsPage />,
          },
          {
            path: "/profile",
            element: <ProfilePage />,
          },
          {
            path: "/settings",
            element: <SettingsPage />,
          },
        ],
      },
    ],
  },
]);

export default router;