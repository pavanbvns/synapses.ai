import React, { useState, useRef } from "react";

const ChatWindow = () => {
  const [query, setQuery] = useState("");
  const [conversation, setConversation] = useState([]); // array of messages (user & AI)
  const [loading, setLoading] = useState(false);
  const outputRef = useRef(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Add user's query as a new message bubble
    setConversation((prev) => [...prev, { sender: "user", text: query }]);
    setLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/chat_with_kb/", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({ user_query: query }),
      });

      if (!response.body) {
        setConversation((prev) => [
          ...prev,
          { sender: "bot", text: "No response received." },
        ]);
        setLoading(false);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let done = false;
      let accumulatedText = ""; // accumulate tokens into one message

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value);
          // If your response is a series of JSON lines, you might want to parse them
          // and extract only the 'content' field. For now, we'll assume chunk is plain text.
          accumulatedText += chunk;
          // Optionally update the UI to show the in-progress response
          setConversation((prev) => {
            const updated = [...prev];
            // Replace the last bot message with the updated text
            if (updated.length > 0 && updated[updated.length - 1].sender === "bot") {
              updated[updated.length - 1].text = accumulatedText;
            } else {
              updated.push({ sender: "bot", text: accumulatedText });
            }
            return updated;
          });
          if (outputRef.current) {
            outputRef.current.scrollTop = outputRef.current.scrollHeight;
          }
        }
      }
    } catch (error) {
      setConversation((prev) => [
        ...prev,
        { sender: "bot", text: `Error: ${error.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit} style={{ marginBottom: "1em" }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask your question..."
          style={{ width: "300px", padding: "0.5em" }}
          required
        />
        <button type="submit" style={{ padding: "0.5em 1em", marginLeft: "1em" }}>
          Send
        </button>
      </form>
      <div
        ref={outputRef}
        style={{
          border: "1px solid #ccc",
          padding: "1em",
          height: "300px",
          overflowY: "auto",
          whiteSpace: "pre-wrap",
          background: "#f9f9f9",
        }}
      >
        {conversation.map((msg, idx) => (
          <div key={idx} style={{ marginBottom: "1em" }}>
            <strong>{msg.sender === "user" ? "You:" : "Bot:"}</strong>
            <div>{msg.text}</div>
          </div>
        ))}
        {loading && <div>Loading...</div>}
      </div>
    </div>
  );
};

export default ChatWindow;
