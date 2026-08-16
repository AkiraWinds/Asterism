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
import { Plus, X } from "@phosphor-icons/react";

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
    <div className="flex h-full flex-col rounded-lg border border-border bg-card">
      <div className="flex items-center gap-1 overflow-x-auto border-b border-border px-2 py-2">
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`group flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-medium ${
              c.id === activeId
                ? "bg-accent text-accent-on"
                : "text-muted-foreground hover:bg-muted"
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
              <X size={12} weight="thin" />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={handleNewChat}
          aria-label="New chat"
          title="New chat"
          className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted"
        >
          <Plus size={12} weight="thin" />
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {loadError && <p className="text-sm text-destructive">{loadError}</p>}
        {turns.map((turn, i) => (
          <div key={i} className={turn.role === "user" ? "text-right" : "text-left"}>
            <p
              className={`inline-block rounded-lg px-3 py-2 text-sm ${
                turn.role === "user" ? "bg-accent text-accent-on" : "bg-muted text-foreground"
              }`}
            >
              {turn.content}
            </p>
            {turn.truncated && <p className="mt-1 text-xs text-destructive">Response interrupted</p>}
          </div>
        ))}
        {sending && streamingText && (
          <div className="text-left">
            <p className="inline-block rounded-lg bg-muted px-3 py-2 text-sm text-foreground">{streamingText}</p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {attachedHighlight && (
        <div className="mx-3 mb-2 flex items-start justify-between gap-2 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
          <span>
            Attached: &quot;{attachedHighlight.slice(0, 80)}
            {attachedHighlight.length > 80 ? "…" : ""}&quot;
          </span>
          <button
            type="button"
            onClick={onClearAttachedHighlight}
            aria-label="Dismiss attached highlight"
            title="Dismiss attached highlight"
            className="shrink-0 rounded px-1 text-muted-foreground hover:text-foreground"
          >
            <X size={12} weight="thin" />
          </button>
        </div>
      )}

      <div className="flex gap-2 border-t border-border p-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          placeholder="Ask about this source…"
          disabled={sending}
          className="flex-1 rounded-md border border-border bg-transparent px-3 py-2 text-sm text-foreground"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={sending || !input.trim()}
          className="rounded-md bg-accent px-3 py-2 text-sm font-medium text-accent-on hover:bg-accent-secondary disabled:opacity-50"
        >
          {sending ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}
