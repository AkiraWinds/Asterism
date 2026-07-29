"use client";

import { useEffect, useRef, useState } from "react";
import { ChatTurn, getChatHistory, streamChatMessage } from "@/lib/api";

export function ChatPanel({ sourceId }: { sourceId: string }) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getChatHistory(sourceId)
      .then(setTurns)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load chat"));
  }, [sourceId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, streamingText]);

  async function handleSend() {
    const message = input.trim();
    if (!message || sending) return;

    setInput("");
    setSending(true);
    setStreamingText("");
    const userTurn: ChatTurn = {
      role: "user",
      content: message,
      attached_highlight: null,
      truncated: false,
      created_at: new Date().toISOString(),
    };
    setTurns((prev) => [...prev, userTurn]);

    try {
      let accumulated = "";
      const { truncated } = await streamChatMessage(sourceId, message, null, (chunk) => {
        accumulated += chunk;
        setStreamingText(accumulated);
      });
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          content: accumulated,
          attached_highlight: null,
          truncated,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setStreamingText("");
      setSending(false);
    }
  }

  return (
    <div className="flex h-full flex-col rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
      <div className="border-b border-neutral-200 px-4 py-3 text-sm font-medium text-neutral-900 dark:border-neutral-800 dark:text-neutral-100">
        Chat
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {loadError && <p className="text-sm text-red-600 dark:text-red-400">{loadError}</p>}
        {turns.map((turn, i) => (
          <div key={i} className={turn.role === "user" ? "text-right" : "text-left"}>
            <p
              className={`inline-block rounded-lg px-3 py-2 text-sm ${
                turn.role === "user"
                  ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
                  : "bg-neutral-100 text-neutral-900 dark:bg-neutral-800 dark:text-neutral-100"
              }`}
            >
              {turn.content}
            </p>
            {turn.truncated && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">Response interrupted</p>
            )}
          </div>
        ))}
        {sending && streamingText && (
          <div className="text-left">
            <p className="inline-block rounded-lg bg-neutral-100 px-3 py-2 text-sm text-neutral-900 dark:bg-neutral-800 dark:text-neutral-100">
              {streamingText}
            </p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="flex gap-2 border-t border-neutral-200 p-3 dark:border-neutral-800">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          placeholder="Ask about this source…"
          disabled={sending}
          className="flex-1 rounded-md border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={sending || !input.trim()}
          className="rounded-md bg-neutral-900 px-3 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-300"
        >
          {sending ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}
