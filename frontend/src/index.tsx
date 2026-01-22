import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import "leaflet/dist/leaflet.css";
import App from "./App";
import reportWebVitals from "./reportWebVitals";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import axios from "axios";

// Configure axios defaults
// Using '/api' as a relative path allows the app to work via Cloudflare tunnel, 
// local IP, or nip.io without hardcoding an address.
const apiUrl = process.env.REACT_APP_API_URL || '/api';
console.log("[Frontend] React App API URL:", apiUrl);
axios.defaults.baseURL = apiUrl;

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
