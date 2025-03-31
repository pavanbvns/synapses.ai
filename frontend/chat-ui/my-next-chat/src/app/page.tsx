import React from "react";
import ChatWindow from "./components/ChatWindow";

export default function HomePage() {
  return (
    <main style={{ margin: "1em", fontFamily: "Arial, sans-serif" }}>
      <h1>Synapses AI Chat</h1>
      <ChatWindow />
    </main>
  );
}
