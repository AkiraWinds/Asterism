"use client";

import { useEffect, useRef, useState } from "react";
import {
  ChatTurn,
  ConversationSummary,
  createConversation,
  deleteConversation,
  getChatHistory,
  listConversations,
  streamChatMessage,
} from "@/lib/api";

export function ChatPanel({
  sourceId,
  attachedHighlight,
  onClearAttachedHighlight,
}: {
  sourceId: string;
  attachedHighlight: string | null;
  onClearAttachedHighlight: () => void;
}) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listConversations(sourceId)
      .then((list) => {
        setConversations(list);
        setActiveId((prev) => prev ?? list[0]?.id ?? null);
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load chats"));
  }, [sourceId]);

  useEffect(() => {
    if (!activeId) return;
    getChatHistory(sourceId, activeId)
      .then(setTurns)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load chat"));
  }, [sourceId, activeId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, streamingText]);

  async function handleNewChat() {
    const created = await createConversation(sourceId);
    setConversations((prev) => [...prev, created]);
    setActiveId(created.id);
  }

  async function handleDeleteChat(id: string) {
    if (!window.confirm("Delete this chat? This can't be undone.")) return;
    const replacement = await deleteConversation(sourceId, id);
    const list = await listConversations(sourceId);
    setConversations(list);
    if (activeId === id) {
      setActiveId(replacement?.id ?? list[0]?.id ?? null);
    }
  }

  async function handleSend() {
    const message = input.trim();
    if (!message || sending || !activeId) return;

    setInput("");
    setSending(true);
    setStreamingText("");
    const userTurn: ChatTurn = {
      role: "user",
      content: message,
      attached_highlight: attachedHighlight,
      truncated: false,
      created_at: new Date().toISOString(),
    };
    setTurns((prev) => [...prev, userTurn]);

    try {
      let accumulated = "";
      const { truncated } = await streamChatMessage(sourceId, activeId, message, attachedHighlight, (chunk) => {
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
      // The highlight was successfully sent as context for this turn — don't
      // let it silently persist and get attached to unrelated future messages.
      onClearAttachedHighlight();
    } catch (err) {
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          content: err instanceof Error ? err.message : "Failed to send message",
          attached_highlight: null,
          truncated: true,
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
      <div className="flex items-center gap-1 overflow-x-auto border-b border-neutral-200 px-2 py-2 dark:border-neutral-800">
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`group flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-medium ${
              c.id === activeId
                ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
                : "text-neutral-500 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
            }`}
          >
            <button type="button" onClick={() => setActiveId(c.id)}>
              {c.title}
            </button>
            <button
              type="button"
              onClick={() => handleDeleteChat(c.id)}
              aria-label={`Delete ${c.title}`}
              className="opacity-0 group-hover:opacity-100"
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={handleNewChat}
          aria-label="New chat"
          title="New chat"
          className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-neutral-500 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
        >
          +
        </button>
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

      {attachedHighlight && (
        <div className="mx-3 mb-2 flex items-start justify-between gap-2 rounded-md bg-neutral-100 px-3 py-2 text-xs text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300">
          <span>
            Attached: &quot;{attachedHighlight.slice(0, 80)}
            {attachedHighlight.length > 80 ? "…" : ""}&quot;
          </span>
          <button
            type="button"
            onClick={onClearAttachedHighlight}
            aria-label="Dismiss attached highlight"
            title="Dismiss attached highlight"
            className="shrink-0 rounded px-1 text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-100"
          >
            ×
          </button>
        </div>
      )}

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
