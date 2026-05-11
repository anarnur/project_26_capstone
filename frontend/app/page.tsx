"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Message = {
  role: "user" | "assistant";
  content: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [language, setLanguage] = useState("Russian");
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setIsLoading(true);
    setStatus("Агент начинает анализ...");

    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company: userMessage, language }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "status") {
              setStatus(data.message);
            } else if (data.type === "chunk") {
              const text = data.content.replace(/\\n/g, "\n");
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  content: updated[updated.length - 1].content + text,
                };
                return updated;
              });
            } else if (data.type === "done") {
              setStatus("");
            } else if (data.type === "error") {
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  content: `Ошибка: ${data.message}`,
                };
                return updated;
              });
            }
          } catch {}
        }
      }
    } catch (e: any) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: `Ошибка соединения: ${e.message}`,
        };
        return updated;
      });
    } finally {
      setIsLoading(false);
      setStatus("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      <header className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center text-zinc-950 font-bold text-sm">
            MI
          </div>
          <div>
            <h1 className="font-semibold text-zinc-100 text-sm">Market Intelligence</h1>
            <p className="text-zinc-500 text-xs">AI-анализ конкурентов</p>
          </div>
        </div>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-emerald-500"
        >
          <option value="Russian">🇷🇺 Русский</option>
          <option value="English">🇬🇧 English</option>
          <option value="Kazakh">🇰🇿 Қазақша</option>
        </select>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6 max-w-4xl mx-auto w-full">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-4 text-center">
            <div className="w-16 h-16 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-2xl">
              🔍
            </div>
            <div>
              <p className="text-zinc-300 font-medium">Введите название компании</p>
              <p className="text-zinc-500 text-sm mt-1">Например: Notion, Linear, Figma, Slack</p>
            </div>
            <div className="flex gap-2 flex-wrap justify-center">
              {["Notion", "Linear", "Figma", "Slack"].map((c) => (
                <button
                  key={c}
                  onClick={() => setInput(c)}
                  className="px-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded-lg text-xs text-zinc-400 hover:border-emerald-500 hover:text-emerald-400 transition-colors"
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-lg bg-emerald-500 flex items-center justify-center text-zinc-950 text-xs font-bold flex-shrink-0 mt-1">
                AI
              </div>
            )}
            <div className={`max-w-2xl rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === "user"
                ? "bg-emerald-600 text-white rounded-tr-sm"
                : "bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-tl-sm"
            }`}>
              {msg.role === "assistant" && msg.content === "" && isLoading ? (
                <div className="flex gap-1 items-center py-1">
                  <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-bounce" style={{animationDelay: "0ms"}} />
                  <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-bounce" style={{animationDelay: "150ms"}} />
                  <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-bounce" style={{animationDelay: "300ms"}} />
                </div>
              ) : (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              )}
            </div>
            {msg.role === "user" && (
              <div className="w-7 h-7 rounded-lg bg-zinc-700 flex items-center justify-center text-zinc-300 text-xs font-bold flex-shrink-0 mt-1">
                U
              </div>
            )}
          </div>
        ))}

        {status && (
          <div className="flex items-center gap-2 text-xs text-zinc-500 pl-10">
            <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
            {status}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="border-t border-zinc-800 px-4 py-4">
        <div className="max-w-4xl mx-auto flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Введите название компании или URL..."
            disabled={isLoading}
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 disabled:opacity-50 transition-colors"
          />
          <button
            onClick={sendMessage}
            disabled={isLoading || !input.trim()}
            className="px-5 py-3 bg-emerald-500 hover:bg-emerald-400 disabled:bg-zinc-700 disabled:text-zinc-500 text-zinc-950 font-semibold text-sm rounded-xl transition-colors"
          >
            {isLoading ? "..." : "Анализ →"}
          </button>
        </div>
        <p className="text-center text-zinc-600 text-xs mt-2">
          Enter для отправки · Shift+Enter для новой строки
        </p>
      </div>
    </main>
  );
}