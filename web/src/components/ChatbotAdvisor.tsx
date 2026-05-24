"use client";

import React, { useState, useRef, useEffect } from "react";
import { askChatbot } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ChatbotAdvisorProps {
  prefill?: {
    type: "single" | "portfolio";
    holding?: { symbol: string; shares: number; buyPrice: number };
    holdings?: { symbol: string; shares: number; buyPrice: number }[];
  } | null;
  onClearPrefill?: () => void;
}

export default function ChatbotAdvisor({ prefill, onClearPrefill }: ChatbotAdvisorProps = {}) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: `### 🤖 Hello! I am your AI Market & Reinvestment Advisor.

I can help you analyze your stock holdings, calculate your current profits or losses, and suggest tailored strategies to recover capital or reinvest efficiently.

**How can I help you today?**
- Click **"Analyze my holding"** on the left to start a conversational step-by-step stock analysis (uses **0 AI tokens** for setup!).
- Ask for short, medium, or long-term **"Loss recovery recommendations"** to scan optimal entry stocks.`
    }
  ]);

  const [input, setInput] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  // Conversational Stock Holding Questionnaire State Machine (0 AI Tokens)
  const [questionStep, setQuestionStep] = useState<"idle" | "ask_symbol" | "ask_shares" | "ask_price">("idle");
  const [tempSymbol, setTempSymbol] = useState<string>("");
  const [tempShares, setTempShares] = useState<number>(0);
  const [tempBuyPrice, setTempBuyPrice] = useState<number>(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (prefill) {
      setQuestionStep("idle");
      setLoading(true);

      if (prefill.type === "single" && prefill.holding) {
        const { symbol, shares, buyPrice } = prefill.holding;
        const userQuery = `Should I stay invested in ${symbol}? (Owned: ${shares} shares bought at ₹${buyPrice})`;

        setMessages(prev => [
          ...prev,
          {
            role: "assistant",
            content: `### 📈 Holding Analysis Triggered from Portfolio\n\nStarting immediate analysis for **${symbol}** (${shares} shares owned, average cost **₹${buyPrice}**)...`
          },
          { role: "user", content: userQuery }
        ]);

        askChatbot(userQuery, symbol, shares, buyPrice)
          .then(res => {
            setMessages(prev => [...prev, { role: "assistant", content: res.response }]);
          })
          .catch(err => {
            console.error(err);
            setMessages(prev => [
              ...prev,
              {
                role: "assistant",
                content: "⚠️ **System Error**: Failed to establish connection with the AI Advisor backend."
              }
            ]);
          })
          .finally(() => {
            setLoading(false);
            if (onClearPrefill) onClearPrefill();
          });
      } else if (prefill.type === "portfolio" && prefill.holdings) {
        const { holdings } = prefill;
        if (holdings.length === 0) {
          setLoading(false);
          if (onClearPrefill) onClearPrefill();
          return;
        }

        const holdingsSummary = holdings.map(h => 
          `• **${h.symbol}**: ${h.shares} shares @ ₹${h.buyPrice.toLocaleString("en-IN")}`
        ).join("\n");

        const userQuery = `Analyze my entire stock portfolio consisting of the following active positions:\n${holdings.map(h => `- ${h.symbol}: ${h.shares} shares bought at avg cost ₹${h.buyPrice}`).join("\n")}\n\nProvide an asset allocation health check, risk assessment, and individual exit/stay recommendations for each stock. Suggest optimal loss recovery reinvestments where appropriate.`;

        setMessages(prev => [
          ...prev,
          {
            role: "assistant",
            content: `### 🤖 Portfolio-Wide AI Analysis Triggered\n\nCompiling comprehensive report for your active holdings:\n\n${holdingsSummary}\n\nRunning cross-asset valuations & scanning recovery recommendations...`
          },
          { role: "user", content: userQuery }
        ]);

        askChatbot(userQuery)
          .then(res => {
            setMessages(prev => [...prev, { role: "assistant", content: res.response }]);
          })
          .catch(err => {
            console.error(err);
            setMessages(prev => [
              ...prev,
              {
                role: "assistant",
                content: "⚠️ **System Error**: Failed to establish connection with the AI Advisor backend."
              }
            ]);
          })
          .finally(() => {
            setLoading(false);
            if (onClearPrefill) onClearPrefill();
          });
      } else {
        setLoading(false);
        if (onClearPrefill) onClearPrefill();
      }
    }
  }, [prefill, onClearPrefill]);

  const handleSendMessage = async (textToSend: string) => {
    if (!textToSend.trim()) return;
    
    setLoading(true);
    const userMsg = textToSend.trim();
    
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setInput("");

    try {
      const res = await askChatbot(userMsg);
      setMessages(prev => [...prev, { role: "assistant", content: res.response }]);
    } catch (err: any) {
      console.error(err);
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: "⚠️ **System Error**: Failed to establish connection with the AI Advisor backend. Please verify your internet connection and try again."
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleQuestionnaireInput = async (val: string) => {
    const cleanInput = val.trim();
    if (!cleanInput) return;

    // Check for exit command
    if (cleanInput.toLowerCase() === "cancel") {
      setQuestionStep("idle");
      setMessages(prev => [
        ...prev,
        { role: "user", content: val },
        {
          role: "assistant",
          content: "🚫 **Onboarding Cancelled**. Holding analysis wizard aborted. You can ask me any regular stock questions now!"
        }
      ]);
      setInput("");
      return;
    }

    if (questionStep === "ask_symbol") {
      const symbol = cleanInput.toUpperCase();
      // Basic stock symbol validation (alphanumeric, dot, dash, e.g. KAYNES.NS)
      if (!/^[A-Z0-9.\-_]{2,20}$/.test(symbol)) {
        setMessages(prev => [
          ...prev,
          { role: "user", content: val },
          {
            role: "assistant",
            content: "⚠️ **Invalid Stock Symbol**. Symbol should contain only alphanumeric characters, dots, or hyphens (e.g. INFY, TCS, KAYNES.NS). Please enter again, or type **'cancel'** to exit:"
          }
        ]);
        setInput("");
        return;
      }

      setTempSymbol(symbol);
      setMessages(prev => [
        ...prev,
        { role: "user", content: val },
        {
          role: "assistant",
          content: `Stock Symbol set to **${symbol}**.\n\nNext, **how many shares of ${symbol} did you buy?** (Enter a number greater than 0):`
        }
      ]);
      setQuestionStep("ask_shares");
      setInput("");
      
    } else if (questionStep === "ask_shares") {
      const shares = parseFloat(cleanInput);
      if (isNaN(shares) || shares <= 0) {
        setMessages(prev => [
          ...prev,
          { role: "user", content: val },
          {
            role: "assistant",
            content: "⚠️ **Invalid Quantity**. Shares owned must be a positive number greater than 0. Please enter a valid number, or type **'cancel'** to exit:"
          }
        ]);
        setInput("");
        return;
      }

      setTempShares(shares);
      setMessages(prev => [
        ...prev,
        { role: "user", content: val },
        {
          role: "assistant",
          content: `Shares quantity set to **${shares}**.\n\nFinally, **what was your average Buy Price (₹) for ${tempSymbol}?** (Enter a number greater than 0):`
        }
      ]);
      setQuestionStep("ask_price");
      setInput("");

    } else if (questionStep === "ask_price") {
      const price = parseFloat(cleanInput);
      if (isNaN(price) || price <= 0) {
        setMessages(prev => [
          ...prev,
          { role: "user", content: val },
          {
            role: "assistant",
            content: "⚠️ **Invalid Buy Price**. Average price must be a positive number greater than 0. Please enter a valid price in ₹, or type **'cancel'** to exit:"
          }
        ]);
        setInput("");
        return;
      }

      setTempBuyPrice(price);
      setQuestionStep("idle");
      setInput("");

      // Start standard AI request flow
      setLoading(true);
      const targetSymbol = tempSymbol;
      const targetShares = tempShares;
      const targetPrice = price;

      const userQuery = `Should I stay invested in ${targetSymbol}? (Owned: ${targetShares} shares bought at ₹${targetPrice})`;
      
      setMessages(prev => [
        ...prev,
        { role: "user", content: `Buy Price: ₹${targetPrice}` },
        { role: "user", content: userQuery }
      ]);

      try {
        const res = await askChatbot(userQuery, targetSymbol, targetShares, targetPrice);
        setMessages(prev => [...prev, { role: "assistant", content: res.response }]);
      } catch (err: any) {
        console.error(err);
        setMessages(prev => [
          ...prev,
          {
            role: "assistant",
            content: "⚠️ **System Error**: Failed to establish connection with the AI Advisor backend. Please verify your internet connection and try again."
          }
        ]);
      } finally {
        setLoading(false);
        setTempSymbol("");
        setTempShares(0);
        setTempBuyPrice(0);
      }
    }
  };

  const handlePredefinedQuery = (type: "recovery" | "holding") => {
    if (type === "recovery") {
      handleSendMessage("Show me high-probability loss recovery stock picks with target prices and stop-losses across 7 days, 30 days, and 6 months.");
    } else {
      setQuestionStep("ask_symbol");
      setTempSymbol("");
      setTempShares(0);
      setTempBuyPrice(0);
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: "### 📈 Stock Holding Analysis\n\nLet's analyze your holding step-by-step to calculate profits/losses and plan a recovery strategy. This operates locally and **uses zero AI tokens** during setup!\n\nFirst, **what is the Stock Symbol**? (e.g. INFY, TCS, KAYNES.NS):"
        }
      ]);
    }
  };

  // Custom premium markdown parsing into rich JSX elements
  const formatBoldText = (text: string) => {
    const parts = text.split(/\*\*([\s\S]*?)\*\*/g);
    return parts.map((part, i) => {
      if (i % 2 === 1) {
        return <strong key={i} className="font-black text-slate-100">{part}</strong>;
      }
      return part;
    });
  };

  const parseMarkdown = (text: string) => {
    const lines = text.split("\n");
    return lines.map((line, idx) => {
      let content = line.trim();
      if (!content) return <div key={idx} className="h-2" />;

      // Header H3
      if (content.startsWith("###")) {
        return (
          <h4 key={idx} className="text-sm font-extrabold text-purple-400 mt-4 mb-2 tracking-wide uppercase flex items-center gap-1.5">
            <span className="w-1.5 h-3 rounded-full bg-purple-500" />
            {content.replace("###", "").trim()}
          </h4>
        );
      }
      
      // Header H4
      if (content.startsWith("####")) {
        return (
          <h5 key={idx} className="text-xs font-bold text-slate-200 mt-3 mb-1.5">
            {content.replace("####", "").trim()}
          </h5>
        );
      }

      // Blockquotes (styled as highly visual, glowing disclaimers)
      if (content.startsWith(">")) {
        const cleanQuote = content.replace(">", "").replace("⚠️", "").replace("DISCLAIMER:", "").replace("STRICT FINANCIAL DISCLAIMER", "").trim();
        return (
          <div key={idx} className="my-4 p-4 border border-rose-500/20 bg-rose-950/15 text-rose-300 rounded-2xl text-[11px] leading-relaxed shadow-[0_0_15px_rgba(239,68,68,0.05)] border-l-4 border-l-rose-500 select-none">
            <span className="font-extrabold block text-rose-400 uppercase tracking-wider mb-1">⚠️ Strict Risk Disclaimer</span>
            {cleanQuote}
          </div>
        );
      }

      // Styled list items
      if (content.startsWith("-") || content.startsWith("*")) {
        const cleanContent = content.substring(1).trim();
        return (
          <li key={idx} className="list-none pl-5 relative text-xs text-slate-300 my-1 leading-relaxed before:content-['•'] before:absolute before:left-1 before:text-purple-400 before:font-bold">
            {formatBoldText(cleanContent)}
          </li>
        );
      }

      // Default text paragraphs
      return (
        <p key={idx} className="text-xs text-slate-300 my-1.5 leading-relaxed">
          {formatBoldText(content)}
        </p>
      );
    });
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-12 items-start mt-4">
      
      {/* Left panel - Predefined commands & holding wizard */}
      <div className="lg:col-span-1 space-y-6">
        
        {/* Helper Panel */}
        <div className="rounded-3xl border border-slate-800 bg-slate-950/60 backdrop-blur-xl p-6 shadow-2xl relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent pointer-events-none" />
          <div className="flex justify-between items-start border-b border-slate-900/60 pb-4 mb-5">
            <div>
              <h3 className="text-md font-extrabold text-slate-100 tracking-wide flex items-center gap-2">
                ⚡ Advisor Quick Prompts
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Fire predefined institutional analytics queries instantly.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <button
              onClick={() => handlePredefinedQuery("holding")}
              className="w-full p-4 rounded-2xl bg-slate-900/30 border border-slate-900 hover:border-purple-500/40 hover:bg-purple-500/5 transition-all text-left flex items-start gap-3 cursor-pointer group/btn shadow-md"
            >
              <div className="h-8 w-8 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center justify-center shrink-0 group-hover/btn:bg-purple-600 group-hover/btn:text-white transition-all shadow-[0_0_10px_rgba(168,85,247,0.1)]">
                📈
              </div>
              <div>
                <span className="text-xs font-extrabold text-slate-200 block">Analyze My Current Holding</span>
                <span className="text-[10px] text-slate-500 mt-0.5 block">Input average buy price, quantity, and analyze whether to stay invested or exit.</span>
              </div>
            </button>

            <button
              onClick={() => handlePredefinedQuery("recovery")}
              className="w-full p-4 rounded-2xl bg-slate-900/30 border border-slate-900 hover:border-purple-500/40 hover:bg-purple-500/5 transition-all text-left flex items-start gap-3 cursor-pointer group/btn shadow-md"
            >
              <div className="h-8 w-8 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center justify-center shrink-0 group-hover/btn:bg-purple-600 group-hover/btn:text-white transition-all shadow-[0_0_10px_rgba(168,85,247,0.1)]">
                🔄
              </div>
              <div>
                <span className="text-xs font-extrabold text-slate-200 block">Loss Reinvestment Scans</span>
                <span className="text-[10px] text-slate-500 mt-0.5 block">Retrieve targeted buy setups across 7-day, 30-day, and 6-month horizons to offset losses.</span>
              </div>
            </button>
          </div>
        </div>

        {/* Onboarding Questionnaire Active Indicator */}
        {questionStep !== "idle" && (
          <div className="rounded-3xl border border-purple-500/25 bg-purple-950/10 p-5 shadow-[0_4px_20px_rgba(168,85,247,0.08)] animate-pulse flex flex-col gap-2">
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-purple-400 flex items-center gap-1.5 select-none">
              ⚡ Questionnaire Mode Active
            </span>
            <p className="text-[11px] text-slate-400 leading-normal">
              Type your answers directly in the chat input below. You can abort at any time by typing <strong className="text-purple-300 font-bold">cancel</strong>.
            </p>
          </div>
        )}

      </div>

      {/* Right panel - Chatbox */}
      <div className="lg:col-span-2 rounded-3xl border border-slate-800 bg-slate-950/60 backdrop-blur-xl shadow-2xl flex flex-col h-[520px] relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent pointer-events-none" />
        
        {/* Chat header */}
        <div className="p-4 border-b border-slate-900 bg-slate-900/10 flex items-center justify-between select-none">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)] animate-pulse" />
            <div>
              <span className="text-xs font-black text-slate-100 tracking-wider uppercase block">AI Strategic Advisor</span>
              <span className="text-[9px] text-slate-500 block mt-0.5">Scans NSE indicators & models in real-time</span>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded text-[8px] font-black tracking-wider uppercase bg-purple-500/10 text-purple-400 border border-purple-500/20">
            LLM Core Active
          </span>
        </div>

        {/* Conversations logs scroll */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 max-h-[380px]">
          {messages.map((m, idx) => {
            const isAI = m.role === "assistant";
            return (
              <div
                key={idx}
                className={`flex gap-3 max-w-[85%] ${
                  isAI ? "self-start text-left mr-auto" : "self-end text-left ml-auto flex-row-reverse"
                }`}
              >
                {/* Avatar Icon */}
                <div
                  className={`h-7 w-7 rounded-full shrink-0 flex items-center justify-center text-xs font-black select-none border shadow-md ${
                    isAI
                      ? "bg-purple-600/10 border-purple-500/20 text-purple-400"
                      : "bg-indigo-600/10 border-indigo-500/20 text-indigo-400"
                  }`}
                >
                  {isAI ? "🤖" : "👤"}
                </div>
                
                {/* Content Bubble */}
                <div
                  className={`p-4 rounded-3xl border shadow-inner ${
                    isAI
                      ? "bg-slate-900/30 border-slate-900/80 rounded-tl-sm text-slate-200"
                      : "bg-purple-500/10 border-purple-500/25 rounded-tr-sm text-slate-100"
                  }`}
                >
                  {isAI ? (
                    <div className="space-y-0.5">{parseMarkdown(m.content)}</div>
                  ) : (
                    <p className="text-xs leading-relaxed">{m.content}</p>
                  )}
                </div>
              </div>
            );
          })}

          {/* Loader when generating response */}
          {loading && (
            <div className="flex gap-3 max-w-[80%] self-start mr-auto">
              <div className="h-7 w-7 rounded-full bg-purple-600/10 border border-purple-500/20 flex items-center justify-center text-xs shrink-0 select-none animate-bounce shadow-md">
                🤖
              </div>
              <div className="bg-slate-900/30 border border-slate-900/80 rounded-3xl rounded-tl-sm p-4 text-slate-400 text-xs flex items-center gap-3">
                <div className="flex space-x-1 items-center h-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                <span>Advisor is scanning indicator outcomes...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input box */}
        <div className="p-4 border-t border-slate-900 bg-slate-950/40 mt-auto">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (questionStep !== "idle") {
                handleQuestionnaireInput(input);
              } else {
                handleSendMessage(input);
              }
            }}
            className="flex items-center gap-2 bg-slate-900/50 border border-slate-900 rounded-2xl px-3 py-1.5 focus-within:ring-1 focus-within:ring-purple-500/30"
          >
            <input
              type="text"
              placeholder={
                questionStep === "ask_symbol"
                  ? "Step 1/3: Enter Stock Symbol (e.g. KAYNES.NS) or type 'cancel'..."
                  : questionStep === "ask_shares"
                  ? `Step 2/3: Enter total shares bought for ${tempSymbol} or type 'cancel'...`
                  : questionStep === "ask_price"
                  ? `Step 3/3: Enter Buy Price (₹) for ${tempSymbol} or type 'cancel'...`
                  : "Ask: 'Is TCS a buy?' or type stock investment queries..."
              }
              disabled={loading}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="flex-1 bg-transparent border-none text-slate-200 text-xs focus:outline-none px-2 h-8"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="h-8 w-8 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-900 text-white rounded-xl flex items-center justify-center transition-all cursor-pointer border border-purple-500/10 shadow-[0_0_10px_rgba(168,85,247,0.2)] shrink-0"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2.5}
                stroke="currentColor"
                className="w-4 h-4"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
              </svg>
            </button>
          </form>
        </div>

      </div>

    </div>
  );
}
