import { useEffect, useRef, useState } from 'react';
import { Sparkles, Plus, Send, ChevronRight, AlertCircle, History, ArrowLeft, Trash2 } from 'lucide-react';
import {
  postChat,
  getSuggestedPrompts,
  getConversations,
  getConversation,
  deleteConversation,
} from '../lib/api.js';
import { useAuth } from '../contexts/AuthContext.jsx';

// ─────────────────────────────────────────────────────────────────────────────
// ChatSidebar
//
// Persistent right rail. Wired to:
//   GET  /chat/suggested-prompts → initial prompt suggestions
//   GET  /chat/conversations     → user's last 10 conversations
//   GET  /chat/conversations/:id → full message history
//   POST /chat                   → message turn (carries conversation_id;
//                                  backend persists both turns to Postgres
//                                  and echoes a fresh suggested_followups list)
//   DEL  /chat/conversations/:id → drop a conversation (cascade)
//
// Two view modes (toggled from the header):
//   - 'chat'    : current conversation thread + input
//   - 'history' : list of recent conversations; click a row to load it
// ─────────────────────────────────────────────────────────────────────────────

export default function ChatSidebar() {
  const { status: authStatus } = useAuth();

  const [view, setView] = useState('chat');         // 'chat' | 'history'
  const [draft, setDraft] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);     // [{role, content, ts, followups?}]
  const [pending, setPending] = useState(false);
  const [sendError, setSendError] = useState(null);

  const [prompts, setPrompts] = useState({ status: 'loading', data: null, error: null });
  const [history, setHistory] = useState({ status: 'idle', data: [], error: null });
  const [historyError, setHistoryError] = useState(null);

  const scrollRef = useRef(null);

  // Initial suggested prompts on mount (only when authenticated; the bearer
  // interceptor would otherwise 401 and bounce the user to /login).
  useEffect(() => {
    if (authStatus !== 'auth') return;
    let cancelled = false;
    getSuggestedPrompts()
      .then((data) => { if (!cancelled) setPrompts({ status: 'ok', data, error: null }); })
      .catch((error) => { if (!cancelled) setPrompts({ status: 'error', data: null, error }); });
    return () => { cancelled = true; };
  }, [authStatus]);

  // Load conversation list on mount + after any change that affects ordering
  // (new conversation, new message, delete). Re-keyed via fetchConversations().
  const fetchConversations = async () => {
    setHistory((h) => ({ ...h, status: h.status === 'idle' ? 'loading' : h.status }));
    try {
      const data = await getConversations();
      setHistory({ status: 'ok', data, error: null });
    } catch (error) {
      setHistory({ status: 'error', data: [], error });
    }
  };

  useEffect(() => {
    if (authStatus !== 'auth') return;
    fetchConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authStatus]);

  // Auto-scroll to bottom whenever messages or pending change.
  useEffect(() => {
    if (view === 'chat' && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, pending, view]);

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
      // Refresh sidebar list so the new conversation surfaces (or the active
      // one bumps to the top with an updated message count).
      fetchConversations();
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
    setView('chat');
  }

  async function loadConversation(id) {
    setHistoryError(null);
    setSendError(null);
    try {
      const conv = await getConversation(id);
      setConversationId(conv.id);
      setMessages(
        (conv.messages || []).map((m) => ({
          role: m.role,
          content: m.content,
          ts: m.created_at,
          followups: [],          // followups are session-scoped; not persisted
          data_sources_used: m.data_sources_used,
        }))
      );
      setView('chat');
    } catch (error) {
      setHistoryError(error?.message || 'Could not load conversation.');
    }
  }

  async function handleDelete(id, title) {
    const label = title || 'this conversation';
    // eslint-disable-next-line no-alert
    if (!window.confirm(`Delete "${label}"? This cannot be undone.`)) return;
    try {
      await deleteConversation(id);
      // If the deleted conversation was the active one, reset the view.
      if (id === conversationId) startNewChat();
      fetchConversations();
    } catch (error) {
      setHistoryError(error?.message || 'Could not delete conversation.');
    }
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
  const hasHistory = (history.data || []).length > 0;

  return (
    <aside className="w-[28%] min-w-[340px] max-w-[460px] shrink-0 border-l border-slate-200 bg-white flex flex-col">
      {/* Header */}
      <div className="h-[60px] shrink-0 px-5 flex items-center justify-between border-b border-slate-200">
        <div className="flex items-center gap-2 min-w-0">
          {view === 'history' ? (
            <button
              onClick={() => setView('chat')}
              className="w-7 h-7 rounded-md bg-navy/5 flex items-center justify-center hover:bg-navy/10 transition-colors"
              aria-label="Back to chat"
              title="Back to chat"
            >
              <ArrowLeft className="w-4 h-4 text-navy" />
            </button>
          ) : (
            <div className="w-7 h-7 rounded-md bg-navy/5 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-gold" />
            </div>
          )}
          <div className="min-w-0">
            <div className="text-sm font-semibold text-navy leading-tight truncate">
              {view === 'history' ? 'Conversations' : 'Assistant'}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">
              {view === 'history' ? `${(history.data || []).length} saved` : 'Live data · Claude'}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {view === 'chat' && (
            <button
              onClick={() => setView('history')}
              className="text-xs text-slate-500 hover:text-navy flex items-center gap-1.5 px-2 py-1.5 rounded-md hover:bg-slate-50 transition-colors"
              aria-label="Show conversation history"
              title={`Conversation history${hasHistory ? ` (${history.data.length})` : ''}`}
            >
              <History className="w-3.5 h-3.5" />
              {hasHistory && <span className="font-mono text-[10px]">{history.data.length}</span>}
            </button>
          )}
          <button
            onClick={startNewChat}
            className="text-xs text-slate-500 hover:text-navy flex items-center gap-1.5 px-2.5 py-1.5 rounded-md hover:bg-slate-50 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            New chat
          </button>
        </div>
      </div>

      {/* History view */}
      {view === 'history' ? (
        <HistoryView
          history={history}
          historyError={historyError}
          activeId={conversationId}
          onPick={loadConversation}
          onDelete={handleDelete}
        />
      ) : (
        <>
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
        </>
      )}
    </aside>
  );
}

// ─── History panel ──────────────────────────────────────────────────────────

function HistoryView({ history, historyError, activeId, onPick, onDelete }) {
  if (history.status === 'loading' || history.status === 'idle') {
    return (
      <div className="flex-1 overflow-y-auto px-5 py-6">
        <div className="flex flex-col gap-2.5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-[58px] rounded-lg bg-slate-100 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (history.status === 'error') {
    return (
      <div className="flex-1 overflow-y-auto px-5 py-6">
        <div className="px-3 py-2.5 rounded-md bg-red-50 ring-1 ring-red-200 text-[12px] text-red-800">
          Couldn't load conversations.
        </div>
      </div>
    );
  }

  if ((history.data || []).length === 0) {
    return (
      <div className="flex-1 overflow-y-auto px-5 py-6">
        <div className="text-[13px] text-slate-500 leading-relaxed">
          No saved conversations yet. Send a message to start one — it'll show
          up here automatically.
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {historyError && (
        <div className="mx-5 mt-4 px-3 py-2 rounded-md bg-red-50 ring-1 ring-red-200 text-[12px] text-red-800">
          {historyError}
        </div>
      )}
      <ul className="divide-y divide-slate-100">
        {history.data.map((c) => (
          <ConversationRow
            key={c.id}
            conv={c}
            isActive={c.id === activeId}
            onPick={() => onPick(c.id)}
            onDelete={() => onDelete(c.id, c.title)}
          />
        ))}
      </ul>
    </div>
  );
}

function ConversationRow({ conv, isActive, onPick, onDelete }) {
  return (
    <li className={`group relative ${isActive ? 'bg-gold/5' : 'hover:bg-slate-50'} transition-colors`}>
      <button
        type="button"
        onClick={onPick}
        className="w-full text-left px-5 py-3 pr-12"
      >
        <div className="text-[13px] text-navy leading-snug truncate">
          {conv.title || 'Untitled conversation'}
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-[10.5px] text-slate-400 font-mono">
          <span>{relativeTime(conv.updated_at)}</span>
          <span className="text-slate-300">·</span>
          <span>{conv.message_count} message{conv.message_count === 1 ? '' : 's'}</span>
          {isActive && (
            <>
              <span className="text-slate-300">·</span>
              <span className="text-gold">active</span>
            </>
          )}
        </div>
      </button>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-md text-slate-300 hover:text-red-600 hover:bg-red-50 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
        aria-label="Delete conversation"
        title="Delete conversation"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </li>
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

// ─── Helpers ────────────────────────────────────────────────────────────────

function relativeTime(iso) {
  if (!iso) return '';
  const then = typeof iso === 'string' ? new Date(iso) : iso;
  const ms = Date.now() - then.getTime();
  if (Number.isNaN(ms)) return '';
  const sec = Math.round(ms / 1000);
  if (sec < 60) return 'just now';
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 7) return `${day}d ago`;
  // Older than a week — use a short date.
  return then.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
