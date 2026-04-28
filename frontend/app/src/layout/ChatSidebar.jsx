import { useState } from 'react';
import { Sparkles, Plus, Send, ChevronRight } from 'lucide-react';

// Step 1 placeholder. Full implementation (POST /chat, suggested-prompts,
// conversation hydration, streaming) lands in Step 6.
export default function ChatSidebar() {
  const [draft, setDraft] = useState('');

  const placeholderPrompts = [
    'What’s wrong with Al Nakheel right now?',
    'Compare risk across all 4 machines',
    'When should I schedule the next maintenance window?',
    'How will Ramadan affect production capacity?',
  ];

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
        <button className="text-xs text-slate-500 hover:text-navy flex items-center gap-1.5 px-2.5 py-1.5 rounded-md hover:bg-slate-50 transition-colors">
          <Plus className="w-3.5 h-3.5" />
          New chat
        </button>
      </div>

      {/* Empty state */}
      <div className="flex-1 overflow-y-auto px-5 py-6">
        <div className="text-sm text-slate-700 leading-relaxed">
          Hi! I can read your live sensor data, machine health, and forecasts.
          Ask me anything.
        </div>

        <div className="mt-5 space-y-2">
          <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400 font-semibold pb-1">
            Suggested
          </div>
          {placeholderPrompts.map((p, i) => (
            <button
              key={i}
              className="w-full text-left text-sm text-slate-700 px-3.5 py-2.5 rounded-lg border border-slate-200 hover:border-gold hover:bg-gold/5 transition-colors flex items-center justify-between gap-2 group"
              disabled
            >
              <span>{p}</span>
              <ChevronRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-gold shrink-0" />
            </button>
          ))}
        </div>

        <div className="mt-6 px-3 py-2.5 rounded-md bg-slate-50 text-[11px] text-slate-500 font-mono">
          Step 6 will wire this to <span className="text-navy">POST /chat</span>.
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-slate-200 p-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setDraft('');
          }}
          className="flex items-end gap-2 rounded-xl border border-slate-200 focus-within:border-navy focus-within:ring-2 focus-within:ring-navy/10 bg-white pl-3.5 pr-2 py-2 transition-all"
        >
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={1}
            placeholder="Ask about machines, alerts, or forecasts…"
            className="flex-1 resize-none text-sm placeholder:text-slate-400 bg-transparent outline-none py-1 max-h-32"
          />
          <button
            type="submit"
            className="shrink-0 w-8 h-8 rounded-md bg-navy text-white hover:bg-navy-800 disabled:bg-slate-200 disabled:text-slate-400 flex items-center justify-center transition-colors"
            disabled={!draft.trim()}
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
