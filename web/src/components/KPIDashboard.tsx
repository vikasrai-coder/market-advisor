"use client";

import React, { useEffect, useState } from "react";
import { Card, Statistic, Progress, Tooltip, ConfigProvider, theme } from "antd";
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  CheckCircleOutlined,
  BulbOutlined,
  SafetyCertificateOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { getDashboardKPI, type KPIData } from "@/lib/api";

interface KPIDashboardProps {
  /** Fallback values from Dashboard parent (used while API loads) */
  recommendationsCount?: number;
  averageScore?: number;
  signalsLoaded?: number;
  isLive?: boolean;
}

export function KPIDashboard({
  recommendationsCount = 0,
  averageScore = 0,
  signalsLoaded = 0,
  isLive = true,
}: KPIDashboardProps) {
  const [pulseAnimation, setPulseAnimation] = useState(true);
  const [kpi, setKpi] = useState<KPIData | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setPulseAnimation((prev) => !prev);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    getDashboardKPI()
      .then(setKpi)
      .catch(() => {});
  }, []);

  // Use real API data if loaded, fall back to parent props
  const recsCount = kpi?.recommendations_count ?? recommendationsCount;
  const avgScore = kpi?.avg_composite_score ?? averageScore;
  const sigCount = kpi?.signals_loaded ?? signalsLoaded;
  const deltaPct = kpi?.delta_pct ?? 0;
  const isDeltaPositive = deltaPct >= 0;
  const winRate = kpi?.system_win_rate;
  const threshold = kpi?.active_threshold ?? 70;
  const warning = kpi?.systemic_warning;

  // Win rate color
  const winRateColor =
    winRate === null || winRate === undefined
      ? "#6B7280"
      : winRate >= 0.65
        ? "#10B981"
        : winRate >= 0.5
          ? "#F59E0B"
          : winRate >= 0.35
            ? "#F97316"
            : "#EF4444";

  const cardStyle = {
    background: "transparent",
    backdropFilter: "blur(10px)",
    boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
    padding: "24px",
  };

  const cardClass =
    "border-[1px] border-[#374151] bg-gradient-to-br from-[#111827] via-[#1F2937] to-[#111827] rounded-xl";

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorBgContainer: "transparent",
        },
      }}
    >
      <div className="w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {/* Recommendations Card */}
        <Card className={cardClass} style={cardStyle}>
          <div className="flex items-center justify-between">
            <div>
              <Statistic
                title={
                  <span className="text-[#9CA3AF] text-sm font-semibold">
                    RECOMMENDATIONS
                  </span>
                }
                value={recsCount}
                valueStyle={{ color: "#10B981", fontSize: "32px" }}
                prefix={<CheckCircleOutlined className="text-[#10B981]" />}
              />
            </div>
            <div className="flex flex-col items-end gap-2">
              <span
                className={`px-3 py-1 ${
                  isDeltaPositive
                    ? "bg-[#10B981]/20 text-[#10B981]"
                    : "bg-[#EF4444]/20 text-[#EF4444]"
                } text-xs font-bold rounded-full flex items-center gap-1`}
              >
                {isDeltaPositive ? (
                  <ArrowUpOutlined className="text-xs" />
                ) : (
                  <ArrowDownOutlined className="text-xs" />
                )}
                {deltaPct > 0 ? "+" : ""}
                {deltaPct}%
              </span>
              <span className="text-[#6B7280] text-xs font-medium">
                vs yesterday
              </span>
            </div>
          </div>
        </Card>

        {/* Average Score Card with Progress Ring */}
        <Card className={cardClass} style={cardStyle}>
          <div className="flex items-center justify-between gap-6">
            <div>
              <p className="text-[#9CA3AF] text-sm font-semibold mb-4">
                AVERAGE SCORE
              </p>
              <Statistic
                value={avgScore}
                valueStyle={{ color: "#8B5CF6", fontSize: "32px" }}
                suffix="%"
              />
            </div>
            <div className="w-24 h-24">
              <Progress
                type="circle"
                percent={avgScore}
                strokeColor="#8B5CF6"
                trailColor="rgba(139, 92, 246, 0.1)"
                size={96}
                format={(percent) => (
                  <span className="text-[#8B5CF6] font-bold">{percent}%</span>
                )}
              />
            </div>
          </div>
        </Card>

        {/* Signals Loaded Card with Live Indicator */}
        <Card className={cardClass} style={cardStyle}>
          <div className="flex items-center justify-between">
            <div>
              <Statistic
                title={
                  <span className="text-[#9CA3AF] text-sm font-semibold">
                    SIGNALS LOADED
                  </span>
                }
                value={sigCount}
                valueStyle={{ color: "#F59E0B", fontSize: "32px" }}
                prefix={<BulbOutlined className="text-[#F59E0B]" />}
              />
            </div>
            <div className="flex flex-col items-end gap-2">
              <div
                className={`w-3 h-3 rounded-full ${
                  isLive ? "bg-[#10B981]" : "bg-[#EF4444]"
                } ${pulseAnimation && isLive ? "animate-pulse" : ""}`}
                title={isLive ? "Live" : "Offline"}
              />
              <span
                className={`text-xs font-semibold ${
                  isLive ? "text-[#10B981]" : "text-[#EF4444]"
                }`}
              >
                {isLive ? "LIVE" : "OFFLINE"}
              </span>
            </div>
          </div>
        </Card>

        {/* System Win Rate Card — NEW */}
        <Card className={cardClass} style={cardStyle}>
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-[#9CA3AF] text-sm font-semibold mb-4">
                SYSTEM WIN RATE
              </p>
              {winRate !== null && winRate !== undefined ? (
                <Statistic
                  value={(winRate * 100).toFixed(1)}
                  valueStyle={{ color: winRateColor, fontSize: "32px" }}
                  suffix="%"
                  prefix={
                    winRate >= 0.5 ? (
                      <SafetyCertificateOutlined style={{ color: winRateColor }} />
                    ) : (
                      <WarningOutlined style={{ color: winRateColor }} />
                    )
                  }
                />
              ) : (
                <Statistic
                  value="—"
                  valueStyle={{ color: "#6B7280", fontSize: "32px" }}
                />
              )}
            </div>
            <Tooltip
              title={
                warning ||
                `Threshold: ${threshold} · Self-learning adjusts quality bar automatically`
              }
            >
              <div className="flex flex-col items-end gap-2">
                <span
                  className={`px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wide uppercase ${
                    threshold >= 85
                      ? "bg-red-500/20 text-red-400 border border-red-500/30"
                      : threshold >= 80
                        ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                        : threshold >= 75
                          ? "bg-sky-500/20 text-sky-400 border border-sky-500/30"
                          : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                  }`}
                >
                  Bar: {threshold}
                </span>
                <span className="text-[#6B7280] text-[10px] font-medium text-right">
                  Auto-Learning
                </span>
              </div>
            </Tooltip>
          </div>
        </Card>
      </div>
    </ConfigProvider>
  );
}
