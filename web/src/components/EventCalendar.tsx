"use client";

import React, { useEffect, useState } from "react";
import { Card, Tag, Spin, ConfigProvider, theme } from "antd";
import { CalendarOutlined, SafetyCertificateOutlined, WarningOutlined } from "@ant-design/icons";
import { getEventCalendar, type EventCalendarResponse } from "@/lib/api";

export default function EventCalendar() {
  const [data, setData] = useState<EventCalendarResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getEventCalendar(14)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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
      <Card
        className={cardClass}
        style={cardStyle}
        title={
          <div className="flex items-center gap-2">
            <CalendarOutlined className="text-amber-400" />
            <span className="text-slate-200 font-bold">Upcoming Market Events & Holidays (Next 14 Days)</span>
          </div>
        }
      >
        {loading ? (
          <div className="flex justify-center py-6">
            <Spin />
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="flex items-center gap-2 text-xs text-emerald-400 py-2">
            <SafetyCertificateOutlined />
            <span>No market closures or high-risk events scheduled in the next 14 days. Clear trading window!</span>
          </div>
        ) : (
          <div className="space-y-2.5">
            {data.items.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-xs"
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono font-bold text-amber-300 bg-amber-950/40 px-2 py-1 rounded border border-amber-500/20">
                    {item.date}
                  </span>
                  <span className="text-slate-200 font-semibold">{item.title}</span>
                </div>
                <Tag color="red" className="!text-[10px] uppercase font-bold tracking-wider">
                  MARKET CLOSED
                </Tag>
              </div>
            ))}
          </div>
        )}
      </Card>
    </ConfigProvider>
  );
}
