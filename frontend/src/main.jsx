import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import "./index.css";
import App from "./App.jsx";

import { ThemeProvider } from "./context/ThemeProvider";
import { AuthProvider } from "./context/AuthContext";
import { ToastProvider } from "./components/ToastProvider";

createRoot(
  document.getElementById("root")
).render(
  <StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  </StrictMode>
);