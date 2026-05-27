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
  Badge,
} from "antd";
import {
  ThunderboltOutlined,
  ReloadOutlined,
  AimOutlined,
  FireOutlined,
  RiseOutlined,
  FallOutlined,
  TrophyOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import {
  adminGetAlphaAlerts,
  adminGetAlphaPerformance,
  adminReconcileAlpha,
  type AlphaAlert,
  type AlphaPerformance,
} from "@/lib/api";

// ── Cap segment badge colors ────────────────────────────────────────────
const CAP_COLORS: Record<string, { bg: string; text: string; border: string }> =
  {
    large: { bg: "#1E3A5F", text: "#60A5FA", border: "#3B82F6" },
    mid: { bg: "#3B1F4B", text: "#C084FC", border: "#A855F7" },
    small: { bg: "#1F3B2D", text: "#6EE7B7", border: "#34D399" },
    unknown: { bg: "#374151", text: "#9CA3AF", border: "#6B7280" },
  };

export default function AlphaAlerts() {
  const [messageApi, contextHolder] = message.useMessage();
  const [alerts, setAlerts] = useState<AlphaAlert[]>([]);
  const [performance, setPerformance] = useState<AlphaPerformance | null>(null);
  const [scanned, setScanned] = useState(0);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [perfLoading, setPerfLoading] = useState(false);
  const [reconciling, setReconciling] = useState(false);

  const loadPerformance = useCallback(async () => {
    setPerfLoading(true);
    try {
      const data = await adminGetAlphaPerformance();
      setPerformance(data);
    } catch {
      // silent — performance panel shows zeroed state
    } finally {
      setPerfLoading(false);
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminGetAlphaAlerts();
      setAlerts(data.alerts ?? []);
      setScanned(data.scanned ?? 0);
      setGeneratedAt(data.generated_at ?? null);
      messageApi.success(
        `Scanned ${data.scanned} stocks — ${data.passed} alpha alerts found`
      );
    } catch (err) {
      messageApi.error("Failed to load alpha alerts");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [messageApi]);

  const handleReconcile = async () => {
    setReconciling(true);
    try {
      const result = await adminReconcileAlpha();
      messageApi.success(
        `Reconciled ${result.reconciled} alerts: ${result.target_hits} hits, ${result.stopped_out} stops, ${result.held} held`
      );
      await loadPerformance();
    } catch {
      messageApi.error("Reconciliation failed");
    } finally {
      setReconciling(false);
    }
  };

  useEffect(() => {
    loadPerformance();
  }, [loadPerformance]);

  return (
    <div className="space-y-6">
      {contextHolder}
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 shadow-lg shadow-amber-500/30">
            <ThunderboltOutlined className="text-lg text-white" />
          </div>
          <div>
            <h2 className="text-xl font-black tracking-tight text-white">
              Alpha Alerts
            </h2>
            <p className="text-xs text-slate-500">
              High-conviction same-day trades · 10%+ target · All cap segments
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            icon={<SyncOutlined spin={reconciling} />}
            onClick={handleReconcile}
            loading={reconciling}
            className="!border-slate-700 !bg-slate-800 !text-slate-300 hover:!bg-slate-700 hover:!text-white"
            size="small"
          >
            Reconcile
          </Button>
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={loadAlerts}
            loading={loading}
            className="!bg-gradient-to-r !from-amber-500 !to-orange-600 !border-none !font-bold !shadow-lg !shadow-amber-500/25 hover:!shadow-amber-500/40"
          >
            Scan Now
          </Button>
        </div>
      </div>

      {/* ── Performance Dashboard ──────────────────────────────────── */}
      <PerformancePanel perf={performance} loading={perfLoading} />

      {/* ── Alerts Grid ────────────────────────────────────────────── */}
      {loading ? (
        <div className="flex min-h-[200px] items-center justify-center rounded-xl border border-slate-800 bg-slate-900/40">
          <div className="text-center">
            <Spin size="large" />
            <p className="mt-3 text-sm text-slate-400">
              Scanning {scanned > 0 ? `${scanned} stocks` : "market"}…
            </p>
          </div>
        </div>
      ) : alerts.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/30 p-8">
          <Empty
            description={
              <span className="text-slate-500">
                {generatedAt
                  ? "No stocks passed the strict alpha filter. Market conditions may not support high-conviction entries right now."
                  : 'Click "Scan Now" to run the alpha scanner across all cap segments.'}
              </span>
            }
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </div>
      ) : (
        <>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>
              {alerts.length} alert{alerts.length !== 1 ? "s" : ""} from{" "}
              {scanned} stocks scanned
            </span>
            {generatedAt && (
              <>
                <span>·</span>
                <span>
                  {new Date(generatedAt).toLocaleTimeString("en-IN", {
                    hour: "2-digit",
                    minute: "2-digit",
                    hour12: true,
                  })}
                </span>
              </>
            )}
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {alerts.map((alert) => (
              <AlertCard key={alert.id} alert={alert} />
            ))}
          </div>
        </>
      )}

      {/* ── Disclaimer ─────────────────────────────────────────────── */}
      <p className="text-[10px] leading-4 text-slate-600">
        ⚠️ DISCLAIMER: This is an analytical screening tool for educational
        purposes only. All outputs carry inherent market risk. The &quot;10%
        target&quot; is a filter threshold, not a guaranteed return. Past
        performance does not predict future results. All trading decisions must
        be made independently.
      </p>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// Sub-components
// ═══════════════════════════════════════════════════════════════════════

function PerformancePanel({
  perf,
  loading,
}: {
  perf: AlphaPerformance | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="flex h-[120px] items-center justify-center rounded-xl border border-slate-800 bg-slate-900/40">
        <Spin size="small" />
      </div>
    );
  }

  const p = perf || {
    total_alerts: 0,
    win_rate: 0,
    avg_return_pct: 0,
    profit_factor: 0,
    training_progress: 0,
    streak: 0,
    streak_type: "none",
    recent_7d_win_rate: 0,
    target_hits: 0,
    stopped_out: 0,
    pending_alerts: 0,
  };

  const progressColor =
    p.training_progress >= 80
      ? "#10B981"
      : p.training_progress >= 40
        ? "#F59E0B"
        : "#EF4444";

  return (
    <div className="rounded-xl border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-800/50 to-slate-900 p-4 sm:p-5">
      {/* Training Progress Bar */}
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <TrophyOutlined className="text-amber-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            System Training Progress
          </span>
        </div>
        <span className="text-xs text-slate-500">
          Avg return: {p.avg_return_pct}% → Target: 10%
        </span>
      </div>
      <Progress
        percent={p.training_progress}
        strokeColor={{
          "0%": "#EF4444",
          "40%": "#F59E0B",
          "80%": "#10B981",
        }}
        trailColor="#1E293B"
        showInfo={false}
        size="small"
        className="mb-4"
      />
      <div className="flex items-center justify-between text-[10px] text-slate-600 mb-5">
        <span>2% baseline</span>
        <span
          className="font-bold"
          style={{ color: progressColor }}
        >
          {p.training_progress}% complete
        </span>
        <span>10% target</span>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <MetricCard
          label="Win Rate"
          value={`${p.win_rate}%`}
          icon={<AimOutlined />}
          color={p.win_rate >= 50 ? "#10B981" : "#F59E0B"}
        />
        <MetricCard
          label="Total Alerts"
          value={String(p.total_alerts)}
          icon={<BarChartOutlined />}
          color="#60A5FA"
        />
        <MetricCard
          label="Profit Factor"
          value={p.profit_factor > 0 ? String(p.profit_factor) : "—"}
          icon={<FireOutlined />}
          color={p.profit_factor >= 2 ? "#10B981" : "#F59E0B"}
        />
        <MetricCard
          label="7d Win Rate"
          value={`${p.recent_7d_win_rate}%`}
          icon={<RiseOutlined />}
          color={p.recent_7d_win_rate >= 50 ? "#10B981" : "#EF4444"}
        />
        <MetricCard
          label="Hits / Stops"
          value={`${p.target_hits} / ${p.stopped_out}`}
          icon={<CheckCircleOutlined />}
          color="#A78BFA"
        />
        <MetricCard
          label="Streak"
          value={
            p.streak > 0
              ? `${p.streak} ${p.streak_type === "win" ? "W" : "L"}`
              : "—"
          }
          icon={
            p.streak_type === "win" ? (
              <RiseOutlined />
            ) : (
              <FallOutlined />
            )
          }
          color={p.streak_type === "win" ? "#10B981" : "#EF4444"}
        />
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2.5">
      <div className="flex items-center gap-1.5 mb-1">
        <span style={{ color }} className="text-sm">
          {icon}
        </span>
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          {label}
        </span>
      </div>
      <p className="text-lg font-black tracking-tight text-white">{value}</p>
    </div>
  );
}

function AlertCard({ alert }: { alert: AlphaAlert }) {
  const cap = CAP_COLORS[alert.cap_segment] || CAP_COLORS.unknown;
  const confidencePct = Math.round(alert.confidence * 100);

  const rewardRisk = alert.stop_pct > 0
    ? (alert.target_pct / alert.stop_pct).toFixed(1)
    : "∞";

  return (
    <div
      className="group relative overflow-hidden rounded-xl border border-slate-700/60 bg-gradient-to-br from-slate-900 via-slate-800/80 to-slate-900 transition-all duration-300 hover:border-amber-500/40 hover:shadow-lg hover:shadow-amber-500/10"
      style={{ animationDelay: `${Math.random() * 200}ms` }}
    >
      {/* Pulsing glow effect */}
      <div className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-amber-500/10 blur-2xl transition-opacity group-hover:opacity-70 opacity-30" />

      <div className="relative p-4">
        {/* Header */}
        <div className="mb-3 flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className="relative">
              <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-lg shadow-emerald-400/50">
                <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400 opacity-75" />
              </span>
              <ThunderboltOutlined className="text-xl text-amber-400" />
            </div>
            <div>
              <h3 className="text-base font-black tracking-tight text-white">
                {alert.display_symbol}
              </h3>
              <p className="text-[10px] text-slate-500 truncate max-w-[140px]">
                {alert.name}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <Tag
              className="!m-0 !border !rounded-md !text-[10px] !font-bold !px-2 !py-0"
              style={{
                backgroundColor: cap.bg,
                color: cap.text,
                borderColor: cap.border,
              }}
            >
              {(alert.cap_segment || "?").toUpperCase()}
            </Tag>
            <Tag className="!m-0 !border-slate-700 !bg-slate-800 !rounded-md !text-[10px] !text-slate-400 !px-2 !py-0">
              {alert.sector}
            </Tag>
          </div>
        </div>

        {/* Price Grid */}
        <div className="mb-3 grid grid-cols-3 gap-2">
          <PriceCell
            label="Entry"
            value={`₹${alert.entry_price.toLocaleString("en-IN")}`}
            color="#60A5FA"
          />
          <PriceCell
            label={`Target (+${alert.target_pct}%)`}
            value={`₹${alert.target_price.toLocaleString("en-IN")}`}
            color="#10B981"
          />
          <PriceCell
            label={`Stop (-${alert.stop_pct}%)`}
            value={`₹${alert.stop_loss.toLocaleString("en-IN")}`}
            color="#EF4444"
          />
        </div>

        {/* Signals Row */}
        <div className="mb-3 flex flex-wrap gap-1.5">
          {alert.macd_crossover && (
            <SignalBadge label="MACD Cross" color="emerald" />
          )}
          {alert.volume_spike && (
            <SignalBadge label="Vol Spike" color="blue" />
          )}
          {alert.vwap && alert.entry_price > alert.vwap && (
            <SignalBadge label="Above VWAP" color="purple" />
          )}
          {alert.rsi && (
            <SignalBadge
              label={`RSI ${alert.rsi}`}
              color={alert.rsi <= 55 ? "amber" : "sky"}
            />
          )}
        </div>

        {/* Confidence & Score Bar */}
        <div className="flex items-center gap-3">
          <Tooltip title={`Composite: ${alert.composite_score}/100`}>
            <div className="flex-1">
              <div className="mb-1 flex items-center justify-between text-[10px]">
                <span className="font-bold text-slate-500">Confidence</span>
                <span className="font-black text-amber-400">
                  {confidencePct}%
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${confidencePct}%`,
                    background: `linear-gradient(90deg, #F59E0B, ${
                      confidencePct >= 80 ? "#10B981" : "#F59E0B"
                    })`,
                  }}
                />
              </div>
            </div>
          </Tooltip>
          <div className="flex items-center gap-1 rounded-md border border-slate-700/50 bg-slate-800/60 px-2 py-1">
            <AimOutlined className="text-[10px] text-slate-500" />
            <span className="text-[10px] font-bold text-slate-400">
              R:R {rewardRisk}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function PriceCell({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="rounded-lg bg-slate-800/50 px-2 py-1.5 text-center">
      <p className="text-[9px] font-bold uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <p className="text-sm font-black" style={{ color }}>
        {value}
      </p>
    </div>
  );
}

function SignalBadge({
  label,
  color,
}: {
  label: string;
  color: "emerald" | "blue" | "purple" | "amber" | "sky";
}) {
  const colors = {
    emerald: "bg-emerald-900/40 text-emerald-300 border-emerald-700/40",
    blue: "bg-blue-900/40 text-blue-300 border-blue-700/40",
    purple: "bg-purple-900/40 text-purple-300 border-purple-700/40",
    amber: "bg-amber-900/40 text-amber-300 border-amber-700/40",
    sky: "bg-sky-900/40 text-sky-300 border-sky-700/40",
  };

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${colors[color]}`}
    >
      <CheckCircleOutlined className="text-[8px]" />
      {label}
    </span>
  );
}
