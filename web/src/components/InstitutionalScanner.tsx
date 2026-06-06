"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";
import {
  runInstitutionalScan,
  getInstitutionalScanStatus,
  type InstitutionalResult,
  type InstitutionalScanResponse,
  type InstitutionalPillarScores,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PILLAR_LABELS: Record<keyof InstitutionalPillarScores, { label: string; emoji: string; color: string }> = {
  trend: { label: "Trend", emoji: "📈", color: "#10B981" },
  momentum: { label: "Momentum", emoji: "⚡", color: "#F59E0B" },
  volume: { label: "Volume", emoji: "📊", color: "#3B82F6" },
  volatility: { label: "Volatility", emoji: "🌊", color: "#8B5CF6" },
  market_structure: { label: "Structure", emoji: "🏗️", color: "#EC4899" },
  relative_strength: { label: "Rel. Strength", emoji: "💪", color: "#06B6D4" },
  institutional: { label: "Institutional", emoji: "🏦", color: "#F97316" },
  news_sentiment: { label: "News", emoji: "📰", color: "#6366F1" },
};

const PILLAR_KEYS = Object.keys(PILLAR_LABELS) as (keyof InstitutionalPillarScores)[];

// ---------------------------------------------------------------------------
// Helper Components
// ---------------------------------------------------------------------------

function AlphaGauge({ value, size = 140 }: { value: number; size?: number }) {
  const radius = (size - 20) / 2;
  const circumference = Math.PI * radius;
  const pct = Math.min(100, Math.max(0, value)) / 100;
  const offset = circumference * (1 - pct);
  const cx = size / 2;
  const cy = size / 2 + 8;

  const color =
    value >= 75 ? "#10B981" : value >= 55 ? "#F59E0B" : value >= 40 ? "#F97316" : "#EF4444";

  return (
    <div className="inst-gauge-container" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Track */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 1 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Value Arc */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 1 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="inst-gauge-arc"
          style={{
            filter: `drop-shadow(0 0 8px ${color}80)`,
            transition: "stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        />
      </svg>
      <div className="inst-gauge-value" style={{ color }}>
        {value.toFixed(0)}
      </div>
      <div className="inst-gauge-label">ALPHA</div>
    </div>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.min(95, Math.max(0, value));
  const color =
    pct >= 75 ? "#10B981" : pct >= 55 ? "#F59E0B" : pct >= 40 ? "#F97316" : "#EF4444";

  return (
    <div className="inst-confidence-bar">
      <div className="inst-confidence-track">
        <div
          className="inst-confidence-fill"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, ${color}40, ${color})`,
            boxShadow: `0 0 12px ${color}60`,
          }}
        />
      </div>
      <div className="inst-confidence-text">
        <span style={{ color }}>{pct.toFixed(0)}%</span>
        <span className="inst-confidence-label">Confidence</span>
      </div>
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict: "BUY" | "HOLD" | "SELL" }) {
  const config = {
    BUY: { bg: "linear-gradient(135deg, #059669, #10B981)", glow: "#10B981", text: "BUY" },
    HOLD: { bg: "linear-gradient(135deg, #D97706, #F59E0B)", glow: "#F59E0B", text: "HOLD" },
    SELL: { bg: "linear-gradient(135deg, #DC2626, #EF4444)", glow: "#EF4444", text: "SELL" },
  }[verdict];

  return (
    <div
      className="inst-verdict-badge"
      style={{
        background: config.bg,
        boxShadow: `0 0 20px ${config.glow}40, 0 0 40px ${config.glow}20`,
      }}
    >
      {config.text}
    </div>
  );
}

function RadarChart({ scores, size = 260 }: { scores: InstitutionalPillarScores; size?: number }) {
  const cx = size / 2;
  const cy = size / 2;
  const maxR = size / 2 - 35;
  const pillars = PILLAR_KEYS;
  const n = pillars.length;
  const step = (2 * Math.PI) / n;
  const offset = -Math.PI / 2; // Start from top

  const getPoint = (i: number, pct: number) => {
    const angle = offset + step * i;
    const r = maxR * pct;
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  };

  // Grid rings
  const rings = [0.25, 0.5, 0.75, 1.0];

  // Data polygon
  const dataPoints = pillars.map((k, i) => {
    const val = (scores[k] || 0) / 100;
    return getPoint(i, val);
  });
  const dataPath = dataPoints.map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`)).join(" ") + " Z";

  return (
    <div className="inst-radar-container">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Grid rings */}
        {rings.map((r) => (
          <polygon
            key={r}
            points={pillars.map((_, i) => { const p = getPoint(i, r); return `${p.x},${p.y}`; }).join(" ")}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth="1"
          />
        ))}
        {/* Spokes */}
        {pillars.map((_, i) => {
          const p = getPoint(i, 1);
          return <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />;
        })}
        {/* Data polygon */}
        <polygon
          points={dataPoints.map((p) => `${p.x},${p.y}`).join(" ")}
          fill="rgba(16, 185, 129, 0.15)"
          stroke="#10B981"
          strokeWidth="2"
          className="inst-radar-data"
          style={{ filter: "drop-shadow(0 0 6px #10B98140)" }}
        />
        {/* Data points */}
        {dataPoints.map((p, i) => {
          const val = scores[pillars[i]] || 0;
          const dotColor = val >= 65 ? "#10B981" : val >= 45 ? "#F59E0B" : "#EF4444";
          return <circle key={i} cx={p.x} cy={p.y} r="4" fill={dotColor} stroke="#0F172A" strokeWidth="1.5" />;
        })}
        {/* Labels */}
        {pillars.map((k, i) => {
          const p = getPoint(i, 1.22);
          const info = PILLAR_LABELS[k];
          return (
            <text
              key={k}
              x={p.x}
              y={p.y}
              textAnchor="middle"
              dominantBaseline="central"
              fill="rgba(255,255,255,0.6)"
              fontSize="9"
              fontWeight="600"
            >
              {info.emoji} {info.label}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

function TradePlanCard({ result }: { result: InstitutionalResult }) {
  const { entry, stop_loss, target_1, target_2, risk_reward } = result;
  const slPct = entry > 0 ? (((entry - stop_loss) / entry) * 100).toFixed(1) : "0";
  const t1Pct = entry > 0 ? (((target_1 - entry) / entry) * 100).toFixed(1) : "0";
  const t2Pct = entry > 0 ? (((target_2 - entry) / entry) * 100).toFixed(1) : "0";

  return (
    <div className="inst-trade-plan">
      <h4 className="inst-trade-plan-title">💰 Trade Plan</h4>
      <div className="inst-trade-levels">
        <div className="inst-level-row">
          <span className="inst-level-label">Entry</span>
          <span className="inst-level-value">₹{entry.toFixed(2)}</span>
        </div>
        <div className="inst-level-row inst-level-sl">
          <span className="inst-level-label">Stop Loss</span>
          <span className="inst-level-value">
            ₹{stop_loss.toFixed(2)}{" "}
            <span className="inst-level-pct" style={{ color: "#EF4444" }}>(-{slPct}%)</span>
          </span>
        </div>
        <div className="inst-level-row inst-level-t1">
          <span className="inst-level-label">Target 1</span>
          <span className="inst-level-value">
            ₹{target_1.toFixed(2)}{" "}
            <span className="inst-level-pct" style={{ color: "#10B981" }}>(+{t1Pct}%)</span>
          </span>
        </div>
        <div className="inst-level-row inst-level-t2">
          <span className="inst-level-label">Target 2</span>
          <span className="inst-level-value">
            ₹{target_2.toFixed(2)}{" "}
            <span className="inst-level-pct" style={{ color: "#10B981" }}>(+{t2Pct}%)</span>
          </span>
        </div>
        <div className="inst-level-row inst-level-rr">
          <span className="inst-level-label">Risk:Reward</span>
          <span className="inst-level-value inst-rr-value">1:{risk_reward.toFixed(1)}</span>
        </div>
      </div>
    </div>
  );
}

function PillarBreakdown({ scores }: { scores: InstitutionalPillarScores }) {
  return (
    <div className="inst-pillar-breakdown">
      {PILLAR_KEYS.map((key) => {
        const info = PILLAR_LABELS[key];
        const val = scores[key] || 0;
        const color = val >= 65 ? "#10B981" : val >= 45 ? "#F59E0B" : "#EF4444";
        return (
          <div key={key} className="inst-pillar-row">
            <div className="inst-pillar-meta">
              <span className="inst-pillar-emoji">{info.emoji}</span>
              <span className="inst-pillar-name">{info.label}</span>
            </div>
            <div className="inst-pillar-bar-container">
              <div
                className="inst-pillar-bar-fill"
                style={{
                  width: `${val}%`,
                  background: `linear-gradient(90deg, ${color}50, ${color})`,
                  boxShadow: `0 0 8px ${color}30`,
                }}
              />
            </div>
            <span className="inst-pillar-score" style={{ color }}>{val.toFixed(0)}</span>
          </div>
        );
      })}
    </div>
  );
}

function StockDetailModal({
  result,
  onClose,
}: {
  result: InstitutionalResult;
  onClose: () => void;
}) {
  return (
    <div className="inst-modal-overlay" onClick={onClose}>
      <div className="inst-modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="inst-modal-close" onClick={onClose}>✕</button>
        <div className="inst-modal-header">
          <div>
            <h2 className="inst-modal-symbol">{result.display_symbol}</h2>
            <p className="inst-modal-name">{result.name} — {result.sector}</p>
          </div>
          <VerdictBadge verdict={result.verdict} />
        </div>

        <div className="inst-modal-scores-row">
          <AlphaGauge value={result.alpha_score} size={120} />
          <div className="inst-modal-confidence-block">
            <ConfidenceBar value={result.confidence_score} />
            <div className="inst-modal-price">₹{result.price.toFixed(2)}</div>
          </div>
        </div>

        <RadarChart scores={result.pillar_scores} size={240} />

        <PillarBreakdown scores={result.pillar_scores} />

        <TradePlanCard result={result} />

        <div className="inst-modal-reasoning">
          <h4>📋 Analysis</h4>
          <p>{result.reasoning}</p>
        </div>
      </div>
    </div>
  );
}

// Mini gauge for table rows
function MiniGauge({ value, size = 36 }: { value: number; size?: number }) {
  const r = (size - 6) / 2;
  const circ = Math.PI * r;
  const pct = Math.min(100, Math.max(0, value)) / 100;
  const color = value >= 70 ? "#10B981" : value >= 50 ? "#F59E0B" : "#EF4444";
  const cx = size / 2;
  const cy = size / 2 + 3;

  return (
    <div style={{ position: "relative", width: size, height: size, display: "inline-block" }}>
      <svg width={size} height={size}>
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 1 1 ${cx + r} ${cy}`}
          fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" strokeLinecap="round"
        />
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 1 1 ${cx + r} ${cy}`}
          fill="none" stroke={color} strokeWidth="3" strokeLinecap="round"
          strokeDasharray={circ} strokeDashoffset={circ * (1 - pct)}
          style={{ transition: "stroke-dashoffset 0.8s ease" }}
        />
      </svg>
      <span style={{
        position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "9px", fontWeight: 800, color, paddingTop: "2px",
      }}>
        {value.toFixed(0)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function InstitutionalScanner() {
  const [scanData, setScanData] = useState<InstitutionalScanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedStock, setSelectedStock] = useState<InstitutionalResult | null>(null);
  const [sortKey, setSortKey] = useState<"alpha_score" | "confidence_score" | "risk_reward">("alpha_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [filterVerdict, setFilterVerdict] = useState<"ALL" | "BUY" | "HOLD" | "SELL">("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  // Load cached scan on mount
  useEffect(() => {
    const loadCachedScan = async () => {
      setLoading(true);
      try {
        const response = await runInstitutionalScan(false);
        if (response.status === "success" && response.results) {
          setScanData(response);
        }
      } catch (e) {
        console.error("[InstitutionalScanner] Failed to load cached scan:", e);
      } finally {
        setLoading(false);
      }
    };
    loadCachedScan();
  }, []);

  const handleScan = useCallback(async () => {
    setLoading(true);
    setError(null);
    setJobStatus("Initializing scan...");
    try {
      const response = await runInstitutionalScan(true);
      if (response.status === "running" && response.job_id) {
        let completed = false;
        const jobId = response.job_id;
        while (!completed) {
          await new Promise((resolve) => setTimeout(resolve, 3000));
          const job = await getInstitutionalScanStatus(jobId);
          if (job.status === "completed" && job.result) {
            setScanData(job.result);
            completed = true;
          } else if (job.status === "failed") {
            throw new Error(job.error || "Scan failed");
          } else if (job.message) {
            setJobStatus(job.message);
          }
        }
      } else {
        setScanData(response);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setLoading(false);
      setJobStatus(null);
    }
  }, []);

  const handleSort = (key: typeof sortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const results = scanData?.results ?? [];
  const filtered = results
    .filter((r) => filterVerdict === "ALL" || r.verdict === filterVerdict)
    .filter((r) => {
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return r.display_symbol.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        r.sector.toLowerCase().includes(q);
    })
    .sort((a, b) => {
      const av = a[sortKey] ?? 0;
      const bv = b[sortKey] ?? 0;
      return sortDir === "desc" ? bv - av : av - bv;
    });

  const alerts = scanData?.alerts ?? [];
  const summary = scanData?.summary;

  return (
    <>
      <style>{INSTITUTIONAL_CSS}</style>

      <div className="inst-scanner">
        {/* Header */}
        <div className="inst-header">
          <div className="inst-header-left">
            <h1 className="inst-title">
              <span className="inst-title-icon">🏛️</span>
              Institutional Scanner
            </h1>
            <p className="inst-subtitle">8-Pillar Alpha Scoring Engine</p>
          </div>
          <button
            className={`inst-scan-btn ${loading ? "inst-scan-btn--loading" : ""}`}
            onClick={handleScan}
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="inst-spinner" />
                {jobStatus || "Scanning..."}
              </>
            ) : (
              <>⚡ Run Institutional Scan</>
            )}
          </button>
        </div>

        {error && (
          <div className="inst-error">{error}</div>
        )}

        {/* Summary Cards */}
        {summary && (
          <div className="inst-summary-grid">
            <div className="inst-summary-card">
              <div className="inst-summary-value">{summary.total_results}</div>
              <div className="inst-summary-label">Stocks Scored</div>
            </div>
            <div className="inst-summary-card inst-summary-card--alert">
              <div className="inst-summary-value">{summary.high_alpha_alerts}</div>
              <div className="inst-summary-label">Alpha Alerts</div>
            </div>
            <div className="inst-summary-card">
              <div className="inst-summary-value" style={{
                color: summary.market_environment === "risk_on" ? "#10B981" :
                  summary.market_environment === "caution" ? "#F59E0B" : "#EF4444",
              }}>
                {summary.market_environment.replace("_", " ").toUpperCase()}
              </div>
              <div className="inst-summary-label">Market</div>
            </div>
            <div className="inst-summary-card">
              <div className="inst-summary-value">{summary.scanned}</div>
              <div className="inst-summary-label">Scanned</div>
            </div>
          </div>
        )}

        {/* High-Alpha Alerts Banner */}
        {alerts.length > 0 && (
          <div className="inst-alerts-banner">
            <h3 className="inst-alerts-title">🔥 High-Alpha Alerts — {alerts.length} stocks qualifying</h3>
            <p className="inst-alerts-subtitle">Alpha &gt; 80 · Confidence &gt; 75 · R:R &gt; 1:2 · Telegram alerts sent</p>
            <div className="inst-alerts-grid">
              {alerts.map((a) => (
                <div
                  key={a.symbol}
                  className="inst-alert-card"
                  onClick={() => setSelectedStock(a)}
                >
                  <div className="inst-alert-card-header">
                    <span className="inst-alert-symbol">{a.display_symbol}</span>
                    <VerdictBadge verdict={a.verdict} />
                  </div>
                  <div className="inst-alert-card-scores">
                    <AlphaGauge value={a.alpha_score} size={80} />
                    <div className="inst-alert-card-details">
                      <ConfidenceBar value={a.confidence_score} />
                      <div className="inst-alert-rr">R:R 1:{a.risk_reward.toFixed(1)}</div>
                      <div className="inst-alert-price">₹{a.price.toFixed(2)}</div>
                    </div>
                  </div>
                  <RadarChart scores={a.pillar_scores} size={160} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Results Table */}
        {results.length > 0 && (
          <div className="inst-results-section">
            {/* Filters */}
            <div className="inst-filters">
              <input
                className="inst-search"
                type="text"
                placeholder="Search symbol, name, or sector..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <div className="inst-verdict-filters">
                {(["ALL", "BUY", "HOLD", "SELL"] as const).map((v) => (
                  <button
                    key={v}
                    className={`inst-verdict-filter-btn ${filterVerdict === v ? "inst-verdict-filter-btn--active" : ""}`}
                    data-verdict={v}
                    onClick={() => setFilterVerdict(v)}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            {/* Table */}
            <div className="inst-table-wrapper">
              <table className="inst-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Symbol</th>
                    <th>Sector</th>
                    <th>Price</th>
                    <th className="inst-th-sortable" onClick={() => handleSort("alpha_score")}>
                      Alpha {sortKey === "alpha_score" ? (sortDir === "desc" ? "↓" : "↑") : ""}
                    </th>
                    <th className="inst-th-sortable" onClick={() => handleSort("confidence_score")}>
                      Conf. {sortKey === "confidence_score" ? (sortDir === "desc" ? "↓" : "↑") : ""}
                    </th>
                    <th>Verdict</th>
                    <th className="inst-th-sortable" onClick={() => handleSort("risk_reward")}>
                      R:R {sortKey === "risk_reward" ? (sortDir === "desc" ? "↓" : "↑") : ""}
                    </th>
                    <th>Pillars</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r, i) => (
                    <tr
                      key={r.symbol}
                      className="inst-table-row"
                      onClick={() => setSelectedStock(r)}
                    >
                      <td className="inst-td-rank">{i + 1}</td>
                      <td>
                        <div className="inst-td-symbol">{r.display_symbol}</div>
                        <div className="inst-td-name">{r.name}</div>
                      </td>
                      <td className="inst-td-sector">{r.sector}</td>
                      <td className="inst-td-price">₹{r.price.toFixed(2)}</td>
                      <td><MiniGauge value={r.alpha_score} /></td>
                      <td><MiniGauge value={r.confidence_score} /></td>
                      <td>
                        <span className={`inst-td-verdict inst-td-verdict--${r.verdict.toLowerCase()}`}>
                          {r.verdict}
                        </span>
                      </td>
                      <td className="inst-td-rr">1:{r.risk_reward.toFixed(1)}</td>
                      <td>
                        <div className="inst-td-pillars">
                          {PILLAR_KEYS.map((k) => {
                            const v = r.pillar_scores[k] || 0;
                            const c = v >= 65 ? "#10B981" : v >= 45 ? "#F59E0B" : "#EF4444";
                            return (
                              <div
                                key={k}
                                className="inst-pillar-dot"
                                title={`${PILLAR_LABELS[k].label}: ${v.toFixed(0)}`}
                                style={{ background: c, boxShadow: `0 0 4px ${c}60` }}
                              />
                            );
                          })}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="inst-table-count">{filtered.length} of {results.length} stocks</div>
          </div>
        )}

        {/* Empty State */}
        {!loading && !scanData && (
          <div className="inst-empty">
            <div className="inst-empty-icon">🏛️</div>
            <h3>Institutional-Grade Analysis</h3>
            <p>Run the 8-pillar scanner to analyze all watchlist stocks with institutional scoring methodology.</p>
            <ul className="inst-empty-list">
              <li>📈 EMA alignment + Supertrend + ADX</li>
              <li>⚡ RSI + MACD + Stochastic RSI</li>
              <li>📊 Volume breakout + Delivery proxy</li>
              <li>🌊 Bollinger Bands + ATR squeeze</li>
              <li>🏗️ Support/Resistance + Breakout detection</li>
              <li>💪 Sector RS + Stock RS vs Nifty</li>
              <li>🏦 Smart money accumulation/distribution</li>
              <li>📰 News sentiment analysis</li>
            </ul>
          </div>
        )}
      </div>

      {/* Stock Detail Modal */}
      {selectedStock && (
        <StockDetailModal result={selectedStock} onClose={() => setSelectedStock(null)} />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// CSS — Premium Glassmorphism Dark Theme
// ---------------------------------------------------------------------------

const INSTITUTIONAL_CSS = `
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

.inst-scanner {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  color: #e2e8f0;
}

/* Header */
.inst-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}
.inst-header-left { display: flex; flex-direction: column; gap: 0.2rem; }
.inst-title {
  font-size: 1.5rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  color: #f8fafc;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.inst-title-icon { font-size: 1.4rem; }
.inst-subtitle {
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

/* Scan Button */
.inst-scan-btn {
  padding: 0.7rem 1.5rem;
  background: linear-gradient(135deg, #059669, #10B981);
  border: none;
  border-radius: 10px;
  color: #fff;
  font-weight: 800;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 20px rgba(16, 185, 129, 0.3);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.inst-scan-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 30px rgba(16, 185, 129, 0.4);
}
.inst-scan-btn:disabled { opacity: 0.7; cursor: not-allowed; }
.inst-scan-btn--loading { background: linear-gradient(135deg, #374151, #4B5563); box-shadow: none; }
.inst-spinner {
  width: 16px; height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: inst-spin 0.8s linear infinite;
}
@keyframes inst-spin { to { transform: rotate(360deg); } }

/* Error */
.inst-error {
  padding: 0.75rem 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #fca5a5;
  font-size: 0.85rem;
  margin-bottom: 1rem;
}

/* Summary Grid */
.inst-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}
@media (max-width: 640px) { .inst-summary-grid { grid-template-columns: repeat(2, 1fr); } }
.inst-summary-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(71, 85, 105, 0.3);
  border-radius: 12px;
  padding: 1rem;
  text-align: center;
  backdrop-filter: blur(12px);
}
.inst-summary-card--alert {
  background: rgba(16, 185, 129, 0.08);
  border-color: rgba(16, 185, 129, 0.3);
}
.inst-summary-value {
  font-size: 1.5rem;
  font-weight: 900;
  color: #f8fafc;
}
.inst-summary-label {
  font-size: 0.65rem;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-top: 0.2rem;
}

/* Alerts Banner */
.inst-alerts-banner {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.06), rgba(6, 182, 212, 0.06));
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 16px;
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}
.inst-alerts-title {
  font-size: 1rem;
  font-weight: 800;
  color: #10B981;
  margin: 0 0 0.25rem;
}
.inst-alerts-subtitle {
  font-size: 0.7rem;
  color: #64748b;
  margin: 0 0 1rem;
}
.inst-alerts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}
.inst-alert-card {
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 12px;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.3s ease;
}
.inst-alert-card:hover {
  border-color: rgba(16, 185, 129, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}
.inst-alert-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}
.inst-alert-symbol { font-size: 1rem; font-weight: 900; color: #f8fafc; }
.inst-alert-card-scores {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.inst-alert-card-details { flex: 1; display: flex; flex-direction: column; gap: 0.3rem; }
.inst-alert-rr { font-size: 0.75rem; font-weight: 700; color: #10B981; }
.inst-alert-price { font-size: 0.85rem; font-weight: 700; color: #cbd5e1; }

/* Results Section */
.inst-results-section { margin-top: 0.5rem; }
.inst-filters {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  align-items: center;
}
.inst-search {
  flex: 1;
  min-width: 200px;
  padding: 0.6rem 1rem;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(71, 85, 105, 0.3);
  border-radius: 8px;
  color: #e2e8f0;
  font-size: 0.8rem;
  outline: none;
  transition: border-color 0.2s;
}
.inst-search:focus { border-color: #10B981; }
.inst-search::placeholder { color: #475569; }
.inst-verdict-filters { display: flex; gap: 0.3rem; }
.inst-verdict-filter-btn {
  padding: 0.45rem 0.8rem;
  border: 1px solid rgba(71, 85, 105, 0.3);
  border-radius: 6px;
  background: rgba(30, 41, 59, 0.4);
  color: #94a3b8;
  font-size: 0.7rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
}
.inst-verdict-filter-btn--active { background: rgba(16, 185, 129, 0.15); border-color: #10B981; color: #10B981; }
.inst-verdict-filter-btn[data-verdict="SELL"].inst-verdict-filter-btn--active {
  background: rgba(239, 68, 68, 0.15); border-color: #EF4444; color: #EF4444;
}
.inst-verdict-filter-btn[data-verdict="HOLD"].inst-verdict-filter-btn--active {
  background: rgba(245, 158, 11, 0.15); border-color: #F59E0B; color: #F59E0B;
}

/* Table */
.inst-table-wrapper {
  overflow-x: auto;
  border: 1px solid rgba(71, 85, 105, 0.25);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(12px);
}
.inst-table { width: 100%; border-collapse: collapse; }
.inst-table th {
  padding: 0.65rem 0.75rem;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
  text-align: left;
  border-bottom: 1px solid rgba(71, 85, 105, 0.25);
  white-space: nowrap;
}
.inst-th-sortable { cursor: pointer; user-select: none; }
.inst-th-sortable:hover { color: #10B981; }
.inst-table-row {
  cursor: pointer;
  transition: background 0.15s;
}
.inst-table-row:hover { background: rgba(16, 185, 129, 0.04); }
.inst-table-row td {
  padding: 0.6rem 0.75rem;
  font-size: 0.8rem;
  border-bottom: 1px solid rgba(71, 85, 105, 0.12);
  white-space: nowrap;
}
.inst-td-rank { color: #475569; font-weight: 600; width: 2rem; }
.inst-td-symbol { font-weight: 800; color: #f8fafc; font-size: 0.85rem; }
.inst-td-name { font-size: 0.65rem; color: #64748b; }
.inst-td-sector { color: #94a3b8; font-size: 0.75rem; }
.inst-td-price { font-weight: 600; color: #cbd5e1; }
.inst-td-verdict {
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-weight: 800;
  font-size: 0.65rem;
  letter-spacing: 0.05em;
}
.inst-td-verdict--buy { background: rgba(16, 185, 129, 0.15); color: #10B981; }
.inst-td-verdict--hold { background: rgba(245, 158, 11, 0.15); color: #F59E0B; }
.inst-td-verdict--sell { background: rgba(239, 68, 68, 0.15); color: #EF4444; }
.inst-td-rr { font-weight: 700; color: #06B6D4; }
.inst-td-pillars { display: flex; gap: 3px; }
.inst-pillar-dot { width: 8px; height: 8px; border-radius: 50%; }
.inst-table-count {
  text-align: right;
  padding: 0.5rem 0.75rem;
  font-size: 0.65rem;
  color: #475569;
}

/* Alpha Gauge */
.inst-gauge-container { position: relative; display: inline-flex; align-items: center; justify-content: center; }
.inst-gauge-value {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -35%);
  font-size: 1.6rem;
  font-weight: 900;
  letter-spacing: -0.03em;
}
.inst-gauge-label {
  position: absolute;
  bottom: 12%;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.55rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: #64748b;
  text-transform: uppercase;
}

/* Confidence Bar */
.inst-confidence-bar { width: 100%; }
.inst-confidence-track {
  height: 6px;
  background: rgba(255,255,255,0.06);
  border-radius: 3px;
  overflow: hidden;
}
.inst-confidence-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 1s ease;
}
.inst-confidence-text {
  display: flex;
  justify-content: space-between;
  margin-top: 0.3rem;
  font-size: 0.75rem;
  font-weight: 700;
}
.inst-confidence-label { color: #64748b; font-size: 0.65rem; }

/* Verdict Badge */
.inst-verdict-badge {
  padding: 0.35rem 0.85rem;
  border-radius: 6px;
  font-weight: 900;
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  color: #fff;
}

/* Radar */
.inst-radar-container { display: flex; justify-content: center; margin: 0.5rem 0; }
.inst-radar-data { transition: all 0.8s ease; }

/* Trade Plan */
.inst-trade-plan {
  background: rgba(30, 41, 59, 0.4);
  border: 1px solid rgba(71, 85, 105, 0.25);
  border-radius: 10px;
  padding: 1rem;
  margin-top: 0.75rem;
}
.inst-trade-plan-title {
  font-size: 0.85rem;
  font-weight: 800;
  color: #f8fafc;
  margin: 0 0 0.75rem;
}
.inst-trade-levels { display: flex; flex-direction: column; gap: 0.4rem; }
.inst-level-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.35rem 0.5rem;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.4);
}
.inst-level-label { font-size: 0.75rem; color: #94a3b8; font-weight: 600; }
.inst-level-value { font-size: 0.8rem; color: #f8fafc; font-weight: 700; }
.inst-level-pct { font-size: 0.7rem; font-weight: 600; }
.inst-rr-value { color: #06B6D4; font-size: 0.9rem; }

/* Pillar Breakdown */
.inst-pillar-breakdown { display: flex; flex-direction: column; gap: 0.4rem; margin-top: 0.75rem; }
.inst-pillar-row { display: flex; align-items: center; gap: 0.5rem; }
.inst-pillar-meta { display: flex; align-items: center; gap: 0.3rem; min-width: 100px; }
.inst-pillar-emoji { font-size: 0.8rem; }
.inst-pillar-name { font-size: 0.7rem; font-weight: 600; color: #94a3b8; }
.inst-pillar-bar-container {
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.06);
  border-radius: 3px;
  overflow: hidden;
}
.inst-pillar-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.8s ease;
}
.inst-pillar-score { min-width: 24px; text-align: right; font-size: 0.7rem; font-weight: 800; }

/* Modal */
.inst-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(8px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  animation: inst-fade-in 0.2s ease;
}
@keyframes inst-fade-in { from { opacity: 0; } to { opacity: 1; } }
.inst-modal-content {
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(71, 85, 105, 0.3);
  border-radius: 16px;
  padding: 1.5rem;
  max-width: 520px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  position: relative;
  animation: inst-slide-up 0.3s ease;
}
@keyframes inst-slide-up { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.inst-modal-close {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  background: rgba(71, 85, 105, 0.3);
  border: none;
  border-radius: 50%;
  width: 28px;
  height: 28px;
  color: #94a3b8;
  font-size: 0.8rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.inst-modal-close:hover { background: rgba(239, 68, 68, 0.3); color: #fca5a5; }
.inst-modal-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; }
.inst-modal-symbol { font-size: 1.3rem; font-weight: 900; color: #f8fafc; margin: 0; }
.inst-modal-name { font-size: 0.75rem; color: #64748b; margin: 0.2rem 0 0; }
.inst-modal-scores-row { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem; }
.inst-modal-confidence-block { flex: 1; display: flex; flex-direction: column; gap: 0.5rem; }
.inst-modal-price { font-size: 1.1rem; font-weight: 800; color: #f8fafc; }
.inst-modal-reasoning {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(30, 41, 59, 0.3);
  border-radius: 8px;
  border: 1px solid rgba(71, 85, 105, 0.2);
}
.inst-modal-reasoning h4 { font-size: 0.8rem; font-weight: 700; color: #cbd5e1; margin: 0 0 0.4rem; }
.inst-modal-reasoning p { font-size: 0.75rem; color: #94a3b8; line-height: 1.5; margin: 0; }

/* Empty State */
.inst-empty {
  text-align: center;
  padding: 3rem 1.5rem;
  background: rgba(30, 41, 59, 0.25);
  border: 1px dashed rgba(71, 85, 105, 0.3);
  border-radius: 16px;
}
.inst-empty-icon { font-size: 3rem; margin-bottom: 0.75rem; }
.inst-empty h3 { font-size: 1.1rem; font-weight: 800; color: #f8fafc; margin: 0 0 0.4rem; }
.inst-empty p { font-size: 0.8rem; color: #64748b; margin: 0 0 1.5rem; max-width: 440px; margin-left: auto; margin-right: auto; }
.inst-empty-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.4rem;
  text-align: left;
  max-width: 540px;
  margin: 0 auto;
}
.inst-empty-list li {
  font-size: 0.75rem;
  color: #94a3b8;
  padding: 0.3rem 0;
}
`;
