"use client";

import { type TradeMode } from "@/lib/api";

type ModeOption = {
  id: TradeMode;
  label: string;
  icon: string;
  shortDesc: string;
  colorClass: string;
  glowClass: string;
};

const MODE_OPTIONS: ModeOption[] = [
  {
    id: "intraday",
    label: "Intraday",
    icon: "⚡",
    shortDesc: "Same-day • 60m MACD",
    colorClass: "border-sky-500/30 text-sky-400 hover:border-sky-400 bg-sky-950/10",
    glowClass: "shadow-[0_0_15px_rgba(56,189,248,0.15)] border-sky-400/80 bg-sky-950/30 text-sky-300",
  },
  {
    id: "swing",
    label: "Swing Trade",
    icon: "📈",
    shortDesc: "Next-day • Daily indicators",
    colorClass: "border-emerald-500/30 text-emerald-400 hover:border-emerald-400 bg-emerald-950/10",
    glowClass: "shadow-[0_0_15px_rgba(16,185,129,0.15)] border-emerald-400/80 bg-emerald-950/30 text-emerald-300",
  },
  {
    id: "longterm",
    label: "Long-term",
    icon: "🏦",
    shortDesc: "1-6 Months • Golden Cross",
    colorClass: "border-purple-500/30 text-purple-400 hover:border-purple-400 bg-purple-950/10",
    glowClass: "shadow-[0_0_15px_rgba(168,85,247,0.15)] border-purple-400/80 bg-purple-950/30 text-purple-300",
  },
];

export function ModeSelector({
  activeMode,
  onChangeMode,
  targetDate,
  onChangeTargetDate,
}: {
  activeMode: TradeMode;
  onChangeMode: (mode: TradeMode) => void;
  targetDate: string;
  onChangeTargetDate: (date: string) => void;
}) {
  return (
    <div className="flex flex-col gap-4 w-full">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {MODE_OPTIONS.map((opt) => {
          const isActive = activeMode === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              onClick={() => onChangeMode(opt.id)}
              className={`flex flex-col items-start gap-1.5 rounded-xl border p-4.5 text-left transition-all duration-350 ease-out cursor-pointer ${
                isActive ? opt.glowClass : opt.colorClass
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-xl leading-none">{opt.icon}</span>
                <span className="font-bold tracking-wide text-sm sm:text-base">{opt.label}</span>
              </div>
              <span className="text-xs text-slate-400 leading-normal">{opt.shortDesc}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
