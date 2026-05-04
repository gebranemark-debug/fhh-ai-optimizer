import { useEffect, useRef, useState } from 'react';
import { Sparkles, Plus, Send, ChevronRight, AlertCircle } from 'lucide-react';
import { postChat, getSuggestedPrompts } from '../lib/api.js';

// ─────────────────────────────────────────────────────────────────────────────
// ChatSidebar
//
// Persistent right rail. Live-wired to:
//   GET  /chat/suggested-prompts → initial prompt suggestions
//   POST /chat                   → message turn (carries conversation_id for
//                                  follow-ups; backend echoes a fresh
//                                  suggested_followups list with each reply)
//
// Conversation state is local to this component. "+ New chat" clears it.
// ─────────────────────────────────────────────────────────────────────────────

export default function ChatSidebar() {
  const [draft, setDraft] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);  // [{role: 'user'|'assistant', content, ts}]
  const [pending, setPending] = useState(false);  // user just sent, awaiting reply
  const [sendError, setSendError] = useState(null);

  const [prompts, setPrompts] = useState({ status: 'loading', data: null, error: null });

  const scrollRef = useRef(null);

  // Fetch initial suggested prompts on mount.
  useEffect(() => {
    let cancelled = false;
    getSuggestedPrompts()
      .then((data) => { if (!cancelled) setPrompts({ status: 'ok', data, error: null }); })
      .catch((error) => { if (!cancelled) setPrompts({ status: 'error', data: null, error }); });
    return () => { cancelled = true; };
  }, []);

  // Auto-scroll to bottom whenever messages or pending change.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, pending]);

  async function sendMessage(text) {
    const trimmed = text.trim();
    if (!trimmed || pending) return;

    setSendError(null);
    setMessages((prev) => [...prev, { role: 'user', content: trimmed, ts: new Date().toISOString() }]);
    setDraft('');
    setPending(true);

    try {
      const res = await postChat(trimmed, conversationId);
      if (res.conversation_id) setConversationId(res.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.reply ?? '(empty reply)',
          ts: res.timestamp ?? new Date().toISOString(),
          followups: res.suggested_followups ?? [],
        },
      ]);
    } catch (error) {
      setSendError(error?.message ?? 'Something went wrong.');
    } finally {
      setPending(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    sendMessage(draft);
  }

  function handleKeyDown(e) {
    // Enter to send, Shift+Enter for newline.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(draft);
    }
  }

  function startNewChat() {
    setConversationId(null);
    setMessages([]);
    setSendError(null);
    setDraft('');
  }

  // The latest assistant turn's followups override the static suggestions
  // (so the prompt rail stays relevant to the conversation flow).
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant');
  const activePrompts = lastAssistant?.followups?.length
    ? lastAssistant.followups
    : prompts.status === 'ok'
      ? prompts.data.prompts
      : [];

  const isEmpty = messages.length === 0 && !pending;

  return (
    <aside className="w-[28%] min-w-[340px] max-w-[460px] shrink-0 border-l border-slate-200 bg-white flex flex-col">
      {/* Header */}
      <div className="h-[60px] shrink-0 px-5 flex items-center justify-between border-b border-slate-200">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-navy/5 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-gold" />
          </div>
          <div>
            <div className="text-sm font-semibold text-navy leading-tight">Assistant</div>
            <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">
              Live data · Claude
            </div>
          </div>
        </div>
        <button
          onClick={startNewChat}
          className="text-xs text-slate-500 hover:text-navy flex items-center gap-1.5 px-2.5 py-1.5 rounded-md hover:bg-slate-50 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          New chat
        </button>
      </div>

      {/* Conversation / empty state */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-6">
        {isEmpty ? (
          <div className="text-sm text-slate-700 leading-relaxed">
            Hi! I can read your live sensor data, machine health, and forecasts.
            Ask me anything.
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {messages.map((m, i) => (
              <ChatBubble key={i} role={m.role} content={m.content} />
            ))}
            {pending && <PendingBubble />}
          </div>
        )}

        {sendError && (
          <div className="mt-4 flex items-start gap-2 px-3 py-2 rounded-md bg-red-50 ring-1 ring-red-200 text-[11.5px] text-red-800">
            <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            <span>{sendError}</span>
          </div>
        )}

        {/* Suggested prompts: shown when empty, OR when the latest assistant
            turn carries followups (rendered below the conversation). */}
        {(isEmpty || lastAssistant?.followups?.length) && activePrompts.length > 0 && (
          <div className="mt-5 space-y-2">
            <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400 font-semibold pb-1">
              {isEmpty ? 'Suggested' : 'Follow-ups'}
            </div>
            {activePrompts.map((p, i) => (
              <button
                key={i}
                onClick={() => sendMessage(p)}
                disabled={pending}
                className="w-full text-left text-sm text-slate-700 px-3.5 py-2.5 rounded-lg border border-slate-200 hover:border-gold hover:bg-gold/5 transition-colors flex items-center justify-between gap-2 group disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span>{p}</span>
                <ChevronRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-gold shrink-0" />
              </button>
            ))}
          </div>
        )}

        {prompts.status === 'error' && isEmpty && (
          <div className="mt-5 px-3 py-2 rounded-md bg-slate-50 text-[11px] text-slate-500 font-mono">
            Couldn't load suggestions — type a question below.
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-slate-200 p-3">
        <form
          onSubmit={handleSubmit}
          className="flex items-end gap-2 rounded-xl border border-slate-200 focus-within:border-navy focus-within:ring-2 focus-within:ring-navy/10 bg-white pl-3.5 pr-2 py-2 transition-all"
        >
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Ask about machines, alerts, or forecasts…"
            disabled={pending}
            className="flex-1 resize-none text-sm placeholder:text-slate-400 bg-transparent outline-none py-1 max-h-32 disabled:opacity-50"
          />
          <button
            type="submit"
            className="shrink-0 w-8 h-8 rounded-md bg-navy text-white hover:bg-navy-800 disabled:bg-slate-200 disabled:text-slate-400 flex items-center justify-center transition-colors"
            disabled={!draft.trim() || pending}
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
        <div className="text-[10px] text-slate-400 mt-1.5 px-1 font-mono">
          Enter to send · Shift+Enter for newline
        </div>
      </div>
    </aside>
  );
}

// ─── Bubbles ────────────────────────────────────────────────────────────────

function ChatBubble({ role, content }) {
  if (role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md px-3.5 py-2.5 bg-navy text-white text-[13px] leading-relaxed whitespace-pre-wrap">
          {content}
        </div>
      </div>
    );
  }
  // Assistant: light bubble, full width, preserve markdown line breaks.
  // No markdown parser yet — the reply renders ** literals and ### headers
  // as text. Acceptable for the v0 demo; can swap react-markdown in later.
  return (
    <div className="flex justify-start">
      <div className="max-w-[95%] rounded-2xl rounded-bl-md px-3.5 py-2.5 bg-slate-50 ring-1 ring-slate-200 text-[13px] leading-relaxed text-slate-700 whitespace-pre-wrap">
        {content}
      </div>
    </div>
  );
}

function PendingBubble() {
  return (
    <div className="flex justify-start">
      <div className="rounded-2xl rounded-bl-md px-3.5 py-3 bg-slate-50 ring-1 ring-slate-200 flex items-center gap-1.5">
        <Dot delay={0} />
        <Dot delay={150} />
        <Dot delay={300} />
      </div>
    </div>
  );
}

function Dot({ delay }) {
  return (
    <span
      className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce"
      style={{ animationDelay: `${delay}ms` }}
    />
  );
}