"use client";

import React, { useEffect, useState } from "react";
import { Card, Statistic, Progress, Space, Empty, ConfigProvider, theme } from "antd";
import {
  ArrowUpOutlined,
  CheckCircleOutlined,
  BulbOutlined,
} from "@ant-design/icons";

interface KPIDashboardProps {
  recommendationsCount?: number;
  averageScore?: number;
  signalsLoaded?: number;
  isLive?: boolean;
}

export function KPIDashboard({
  recommendationsCount = 10,
  averageScore = 81,
  signalsLoaded = 50,
  isLive = true,
}: KPIDashboardProps) {
  const [pulseAnimation, setPulseAnimation] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setPulseAnimation((prev) => !prev);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorBgContainer: "transparent",
        },
      }}
    >
      <div className="w-full grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {/* Recommendations Card */}
        <Card
          className="border-[1px] border-[#374151] bg-gradient-to-br from-[#111827] via-[#1F2937] to-[#111827] rounded-xl"
          style={{
            background: "transparent",
            backdropFilter: "blur(10px)",
            boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
            padding: "24px",
          }}
        >
          <div className="flex items-center justify-between">
            <div>
              <Statistic
                title={
                  <span className="text-[#9CA3AF] text-sm font-semibold">
                    RECOMMENDATIONS
                  </span>
                }
                value={recommendationsCount}
                valueStyle={{ color: "#10B981", fontSize: "32px" }}
                prefix={<CheckCircleOutlined className="text-[#10B981]" />}
              />
            </div>
            <div className="flex flex-col items-end gap-2">
              <span className="px-3 py-1 bg-[#10B981]/20 text-[#10B981] text-xs font-bold rounded-full flex items-center gap-1">
                <ArrowUpOutlined className="text-xs" />
                +12%
              </span>
              <span className="text-[#6B7280] text-xs font-medium">vs yesterday</span>
            </div>
          </div>
        </Card>

        {/* Average Score Card with Progress Ring */}
        <Card
          className="border-[1px] border-[#374151] bg-gradient-to-br from-[#111827] via-[#1F2937] to-[#111827] rounded-xl"
          style={{
            background: "transparent",
            backdropFilter: "blur(10px)",
            boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
            padding: "24px",
          }}
        >
          <div className="flex items-center justify-between gap-6">
            <div>
              <p className="text-[#9CA3AF] text-sm font-semibold mb-4">
                AVERAGE SCORE
              </p>
              <Statistic
                value={averageScore}
                valueStyle={{ color: "#8B5CF6", fontSize: "32px" }}
                suffix="%"
              />
            </div>
            <div className="w-24 h-24">
              <Progress
                type="circle"
                percent={averageScore}
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
        <Card
          className="border-[1px] border-[#374151] bg-gradient-to-br from-[#111827] via-[#1F2937] to-[#111827] rounded-xl"
          style={{
            background: "transparent",
            backdropFilter: "blur(10px)",
            boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
            padding: "24px",
          }}
        >
          <div className="flex items-center justify-between">
            <div>
              <Statistic
                title={
                  <span className="text-[#9CA3AF] text-sm font-semibold">
                    SIGNALS LOADED
                  </span>
                }
                value={signalsLoaded}
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
              <span className={`text-xs font-semibold ${
                isLive ? "text-[#10B981]" : "text-[#EF4444]"
              }`}>
                {isLive ? "LIVE" : "OFFLINE"}
              </span>
            </div>
          </div>
        </Card>
      </div>
    </ConfigProvider>
  );
}
