import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import "leaflet/dist/leaflet.css";
import "./auth/supertokens";
import App from "./App";
import reportWebVitals from "./reportWebVitals";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import axios from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SuperTokensWrapper } from "supertokens-auth-react";

// Configure axios defaults
// Using '/api' as a relative path allows the app to work via Cloudflare tunnel, 
// local IP, or nip.io without hardcoding an address.
const apiUrl = process.env.REACT_APP_API_URL || '/api';
console.log("[Frontend] React App API URL:", apiUrl);
axios.defaults.baseURL = apiUrl;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 30_000,
      retry: 1,
    },
  },
});

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <SuperTokensWrapper>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </SuperTokensWrapper>
    </QueryClientProvider>
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
