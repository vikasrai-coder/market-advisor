"use client";

import type { Recommendation } from "@/lib/api";

type SectorGroup = {
  name: string;
  count: number;
  avgScore: number;
  symbols: string[];
};

export function SectorHeatmap({ recs }: { recs: Recommendation[] }) {
  if (!recs.length) return null;

  // Group by sector
  const groups: Record<string, SectorGroup> = {};

  recs.forEach((r) => {
    const rawSector = r.stocks?.sector || r.cap_segment || "Other";
    const sectorName = rawSector.trim() ? rawSector : "Other";

    if (!groups[sectorName]) {
      groups[sectorName] = {
        name: sectorName,
        count: 0,
        avgScore: 0,
        symbols: [],
      };
    }

    groups[sectorName].count += 1;
    groups[sectorName].avgScore += r.composite_score;
    groups[sectorName].symbols.push(r.symbol.replace(".NS", "").replace(".BO", ""));
  });

  // Calculate averages & convert to array
  const sectorList = Object.values(groups).map((g) => ({
    ...g,
    avgScore: Math.round((g.avgScore / g.count) * 10) / 10,
  }));

  // Sort by count desc, then average score desc
  sectorList.sort((a, b) => b.count - a.count || b.avgScore - a.avgScore);

  // Curated color grids based on average sector score
  const getSectorColor = (score: number) => {
    if (score >= 80) return "from-emerald-500/10 to-teal-500/10 border-emerald-500/30 text-emerald-400";
    if (score >= 75) return "from-sky-500/10 to-blue-500/10 border-sky-500/30 text-sky-400";
    if (score >= 70) return "from-purple-500/10 to-indigo-500/10 border-purple-500/30 text-purple-400";
    return "from-slate-500/10 to-slate-600/10 border-slate-700 text-slate-400";
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/20 p-6 mb-8">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-white tracking-wide">🔥 Sector Heatmap & Capital Flow</h2>
          <p className="text-xs text-slate-400 mt-0.5">Identifies where institutional capital is concentrated across active picks.</p>
        </div>
        <span className="rounded bg-slate-950 border border-slate-800 px-2 py-0.5 text-xxs font-bold text-slate-400">
          {sectorList.length} Active Sectors
        </span>
      </div>

      <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 md:grid-cols-3">
        {sectorList.map((sec) => (
          <div
            key={sec.name}
            className={`flex flex-col justify-between rounded-lg border bg-gradient-to-br p-4.5 transition hover:scale-[1.01] duration-300 ${getSectorColor(
              sec.avgScore
            )}`}
          >
            <div>
              <div className="flex items-start justify-between">
                <span className="font-bold text-sm text-slate-100 line-clamp-1">{sec.name}</span>
                <span className="rounded-full bg-slate-950 px-2 py-0.5 text-xxs font-bold text-slate-400 whitespace-nowrap border border-slate-800">
                  {sec.count} {sec.count === 1 ? "pick" : "picks"}
                </span>
              </div>
              <div className="mt-3.5 flex flex-wrap gap-1">
                {sec.symbols.map((sym) => (
                  <span key={sym} className="rounded bg-slate-900/60 px-1.5 py-0.5 text-[10px] text-slate-300 border border-slate-800/40">
                    {sym}
                  </span>
                ))}
              </div>
            </div>
            <div className="mt-4 flex items-baseline justify-between border-t border-slate-800/40 pt-2.5">
              <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Avg Strength</span>
              <span className="text-base font-black tracking-tight">{sec.avgScore.toFixed(1)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
