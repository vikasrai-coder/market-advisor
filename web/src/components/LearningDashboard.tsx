"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Card,
  Spin,
  Button,
  Tag,
  Progress,
  Tooltip,
  Empty,
  message,
  ConfigProvider,
  theme,
} from "antd";
import {
  ExperimentOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  WarningOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  RiseOutlined,
  FallOutlined,
} from "@ant-design/icons";
import {
  getLearningReport,
  triggerLearning,
  type LearningReport,
} from "@/lib/api";

// ── Helpers ──────────────────────────────────────────────────────────────

function winRateColor(wr: number): string {
  if (wr >= 0.65) return "#10B981";
  if (wr >= 0.5) return "#F59E0B";
  if (wr >= 0.35) return "#F97316";
  return "#EF4444";
}

function thresholdBadge(t: number) {
  if (t >= 85) return { label: "STRICT", color: "#EF4444", bg: "rgba(239,68,68,0.15)" };
  if (t >= 80) return { label: "CAUTIOUS", color: "#F97316", bg: "rgba(249,115,22,0.15)" };
  if (t >= 75) return { label: "NORMAL", color: "#3B82F6", bg: "rgba(59,130,246,0.15)" };
  return { label: "RELAXED", color: "#10B981", bg: "rgba(16,185,129,0.15)" };
}

function formatDate(iso: string | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// ── Component ────────────────────────────────────────────────────────────

export default function LearningDashboard() {
  const [messageApi, contextHolder] = message.useMessage();
  const [report, setReport] = useState<LearningReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);

  const loadReport = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getLearningReport();
      setReport(data);
    } catch (err: any) {
      messageApi.error(err.message || "Failed to load learning report");
    } finally {
      setLoading(false);
    }
  }, [messageApi]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      const res = await triggerLearning();
      messageApi.success(res.message || "Learning brain re-analyzed!");
      loadReport();
    } catch (err: any) {
      messageApi.error(err.message || "Failed to trigger learning");
    } finally {
      setTriggering(false);
    }
  };

  const cs = report?.current_state;
  const history = report?.history || [];
  const winRate = cs?.overall_win_rate ?? null;
  const threshold = cs?.min_composite_score_override ?? 70;
  const tBadge = thresholdBadge(threshold);
  const sectorRates = cs?.sector_win_rates ?? {};
  const modeRates = cs?.mode_win_rates ?? {};
  const suppressedSectors = cs?.suppressed_sectors ?? [];
  const suppressedModes = cs?.suppressed_trade_modes ?? [];

  const cardStyle: React.CSSProperties = {
    background: "transparent",
    backdropFilter: "blur(10px)",
    boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
  };

  const cardClass =
    "border-[1px] border-[#374151] bg-gradient-to-br from-[#111827] via-[#1F2937] to-[#111827] rounded-xl";

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: { colorBgContainer: "transparent" },
      }}
    >
      {contextHolder}
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ExperimentOutlined className="text-2xl text-cyan-400" />
            <div>
              <h2 className="text-xl font-bold text-white">Self-Learning Brain</h2>
              <p className="text-sm text-slate-400">
                Auto-calibrates signal quality based on 30-day rolling performance
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              icon={<ReloadOutlined />}
              onClick={loadReport}
              loading={loading}
              className="!bg-slate-800 !text-slate-300 !border-slate-700 hover:!bg-slate-700"
            >
              Refresh
            </Button>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={handleTrigger}
              loading={triggering}
              className="!bg-cyan-600 hover:!bg-cyan-500 !border-cyan-500"
            >
              Force Re-Learn Now
            </Button>
          </div>
        </div>

        {loading && !report ? (
          <div className="flex justify-center py-20">
            <Spin size="large" />
          </div>
        ) : !cs ? (
          <Empty description="No learning data available yet" />
        ) : (
          <>
            {/* Systemic Warning Banner */}
            {cs.systemic_warning && (
              <div
                className={`rounded-lg px-4 py-3 text-sm font-medium flex items-center gap-2 ${
                  threshold >= 85
                    ? "bg-red-950/40 border border-red-500/30 text-red-300"
                    : threshold >= 80
                      ? "bg-amber-950/40 border border-amber-500/30 text-amber-300"
                      : "bg-sky-950/40 border border-sky-500/30 text-sky-300"
                }`}
              >
                <WarningOutlined />
                {cs.systemic_warning}
              </div>
            )}

            {/* Top-Level Gauges */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {/* Win Rate Gauge */}
              <Card className={cardClass} style={cardStyle}>
                <div className="text-center">
                  <p className="text-[#9CA3AF] text-xs font-semibold mb-3">30-DAY WIN RATE</p>
                  <Progress
                    type="circle"
                    percent={winRate !== null ? Math.round(winRate * 100) : 0}
                    strokeColor={winRate !== null ? winRateColor(winRate) : "#6B7280"}
                    trailColor="rgba(255,255,255,0.06)"
                    size={100}
                    format={(pct) => (
                      <span style={{ color: winRate !== null ? winRateColor(winRate) : "#6B7280", fontWeight: 800, fontSize: 22 }}>
                        {pct}%
                      </span>
                    )}
                  />
                </div>
              </Card>

              {/* Active Threshold */}
              <Card className={cardClass} style={cardStyle}>
                <div className="text-center">
                  <p className="text-[#9CA3AF] text-xs font-semibold mb-3">QUALITY THRESHOLD</p>
                  <p className="text-4xl font-black" style={{ color: tBadge.color }}>
                    {threshold}
                  </p>
                  <Tag
                    className="mt-2"
                    style={{
                      background: tBadge.bg,
                      color: tBadge.color,
                      border: `1px solid ${tBadge.color}30`,
                      fontWeight: 700,
                      fontSize: 10,
                    }}
                  >
                    {tBadge.label}
                  </Tag>
                </div>
              </Card>

              {/* Sample Size */}
              <Card className={cardClass} style={cardStyle}>
                <div className="text-center">
                  <p className="text-[#9CA3AF] text-xs font-semibold mb-3">SAMPLE SIZE</p>
                  <p className="text-4xl font-black text-slate-200">{cs.sample_size ?? 0}</p>
                  <p className="text-[10px] text-slate-500 mt-1">resolved trades analyzed</p>
                </div>
              </Card>

              {/* Last Updated */}
              <Card className={cardClass} style={cardStyle}>
                <div className="text-center">
                  <p className="text-[#9CA3AF] text-xs font-semibold mb-3">LAST UPDATED</p>
                  <ClockCircleOutlined className="text-3xl text-slate-400 mb-2" />
                  <p className="text-xs text-slate-300 font-medium">{formatDate(cs.generated_at)}</p>
                </div>
              </Card>
            </div>

            {/* Sector Win Rates */}
            <Card className={cardClass} style={cardStyle} title={<span className="text-slate-200 font-bold">📊 Sector Win Rates</span>}>
              {Object.keys(sectorRates).length === 0 ? (
                <p className="text-slate-500 text-sm">No sector data available yet</p>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {Object.entries(sectorRates)
                    .sort(([, a], [, b]) => b - a)
                    .map(([sector, wr]) => {
                      const isSuppressed = suppressedSectors.includes(sector);
                      return (
                        <div
                          key={sector}
                          className={`rounded-lg p-3 border ${
                            isSuppressed
                              ? "border-red-500/30 bg-red-950/20"
                              : wr >= 0.65
                                ? "border-emerald-500/20 bg-emerald-950/10"
                                : wr >= 0.5
                                  ? "border-amber-500/20 bg-amber-950/10"
                                  : "border-slate-700 bg-slate-800/30"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-slate-300 font-semibold truncate">{sector}</span>
                            {isSuppressed && (
                              <Tag color="red" className="!text-[9px] !px-1 !py-0 !m-0">SUPPRESSED</Tag>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <Progress
                              percent={Math.round(wr * 100)}
                              size="small"
                              strokeColor={winRateColor(wr)}
                              trailColor="rgba(255,255,255,0.06)"
                              showInfo={false}
                              className="flex-1"
                            />
                            <span
                              className="text-sm font-bold"
                              style={{ color: winRateColor(wr) }}
                            >
                              {(wr * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                      );
                    })}
                </div>
              )}
            </Card>

            {/* Mode Win Rates */}
            <Card className={cardClass} style={cardStyle} title={<span className="text-slate-200 font-bold">⚡ Trade Mode Win Rates</span>}>
              {Object.keys(modeRates).length === 0 ? (
                <p className="text-slate-500 text-sm">No mode data available yet</p>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(modeRates).map(([mode, wr]) => {
                    const isSuppressed = suppressedModes.includes(mode);
                    return (
                      <div
                        key={mode}
                        className={`rounded-lg p-4 border text-center ${
                          isSuppressed
                            ? "border-red-500/30 bg-red-950/20"
                            : "border-slate-700 bg-slate-800/20"
                        }`}
                      >
                        <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-2">{mode}</p>
                        <p className="text-2xl font-black" style={{ color: winRateColor(wr) }}>
                          {(wr * 100).toFixed(0)}%
                        </p>
                        {isSuppressed && (
                          <Tag color="red" className="mt-1 !text-[9px]">SUPPRESSED</Tag>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>

            {/* Learning History Timeline */}
            <Card className={cardClass} style={cardStyle} title={<span className="text-slate-200 font-bold">📈 Learning History</span>}>
              {history.length === 0 ? (
                <p className="text-slate-500 text-sm">No learning history recorded yet. Click &quot;Force Re-Learn Now&quot; to create the first snapshot.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700">
                        <th className="text-left py-2 px-3 text-slate-400 font-semibold text-xs">Date</th>
                        <th className="text-center py-2 px-3 text-slate-400 font-semibold text-xs">Win Rate</th>
                        <th className="text-center py-2 px-3 text-slate-400 font-semibold text-xs">Threshold</th>
                        <th className="text-center py-2 px-3 text-slate-400 font-semibold text-xs">Sample</th>
                        <th className="text-left py-2 px-3 text-slate-400 font-semibold text-xs">Suppressed</th>
                        <th className="text-left py-2 px-3 text-slate-400 font-semibold text-xs">Warning</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.slice(0, 20).map((entry, idx) => (
                        <tr key={entry.id} className={`border-b border-slate-800/50 ${idx === 0 ? "bg-cyan-950/10" : ""}`}>
                          <td className="py-2 px-3 text-slate-300 text-xs">{formatDate(entry.generated_at)}</td>
                          <td className="py-2 px-3 text-center">
                            <span className="font-bold" style={{ color: entry.overall_win_rate !== null ? winRateColor(entry.overall_win_rate) : "#6B7280" }}>
                              {entry.overall_win_rate !== null ? `${(entry.overall_win_rate * 100).toFixed(1)}%` : "—"}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-center">
                            <span className="font-bold text-slate-200">{entry.min_composite_override ?? "—"}</span>
                          </td>
                          <td className="py-2 px-3 text-center text-slate-400">{entry.sample_size}</td>
                          <td className="py-2 px-3 text-xs">
                            {[...(entry.suppressed_sectors || []), ...(entry.suppressed_modes || [])].length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {[...(entry.suppressed_sectors || []), ...(entry.suppressed_modes || [])].map((s) => (
                                  <Tag key={s} color="red" className="!text-[9px] !m-0">{s}</Tag>
                                ))}
                              </div>
                            ) : (
                              <span className="text-slate-600">None</span>
                            )}
                          </td>
                          <td className="py-2 px-3 text-xs text-slate-400 max-w-[200px] truncate">{entry.systemic_warning || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </>
        )}
      </div>
    </ConfigProvider>
  );
}
