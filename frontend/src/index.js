import React from "react";
import ReactDOM from "react-dom";
import { BrowserRouter, Routes, Route } from "react-router";
import "./index.css";
import App from "./App";
import reportWebVitals from "./reportWebVitals";
import TopCards from "./components/TopCards";
import TopDecks from "./components/TopDecks";
import Battles from "./components/Battles";

const root = document.getElementById("root");

ReactDOM.createRoot(root).render(
    <React.StrictMode>
        <BrowserRouter>
            <Routes>
                <Route index element={<App component={TopCards} />} />
                <Route path="decks" element={<App component={TopDecks} />} />
                <Route path="battles" element={<App component={Battles} />} />
            </Routes>
        </BrowserRouter>
    </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();

// Cache Clash Royale card icons via a tiny service worker.
if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker
            .register("/sw.js")
            .catch((err) => console.error("SW registration failed:", err));
    });
}
