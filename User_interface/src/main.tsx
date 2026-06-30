import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import "@/styles/variables.css";
import "@/styles/globals.css";
import "@/styles/layout.css";
import "@/styles/utilities.css";
import "@/styles/animations.css";
import "@/auth/auth.css";
import "./styles/global.css";

import AppProviders from "./app/providers";
import { router } from "./app/router";

import { authService } from "@/auth/auth-service";

// Restore persisted authentication before React renders.
authService.restoreSession();

ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement,
).render(
  <React.StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </React.StrictMode>,
);