import React from "react"; import { createRoot } from "react-dom/client"; import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"; import App from "./App"; import { LangProvider } from "./i18n"; import "./index.css";
createRoot(document.getElementById("root")).render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, "")}><LangProvider><App /></LangProvider></BrowserRouter></QueryClientProvider>);
