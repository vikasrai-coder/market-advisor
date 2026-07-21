"use client";

import React from "react";
import { Segmented, Space } from "antd";
import {
  BarChartOutlined,
  BulbOutlined,
  DiffOutlined,
  FolderOutlined,
  RobotOutlined,
  LineChartOutlined,
  LockOutlined,
  ThunderboltOutlined,
  PartitionOutlined,
  ExperimentOutlined,
} from "@ant-design/icons";

type ModuleTab =
  | "scans"
  | "signals"
  | "backtest"
  | "portfolio"
  | "chatbot"
  | "pennyscans"
  | "alpha"
  | "institutional"
  | "mindmap"
  | "learning"
  | "admin";

interface ModuleNavigationProps {
  activeTab: ModuleTab;
  onTabChange: (tab: ModuleTab) => void;
  isAdminMode?: boolean;
}

export function ModuleNavigation({
  activeTab,
  onTabChange,
  isAdminMode = false,
}: ModuleNavigationProps) {
  const items = [
    { id: "scans", label: "SCANS", icon: <BarChartOutlined /> },
    { id: "signals", label: "SIGNALS", icon: <BulbOutlined /> },
    { id: "backtest", label: "BACKTEST", icon: <DiffOutlined /> },
    { id: "portfolio", label: "PORTFOLIO", icon: <FolderOutlined /> },
    { id: "chatbot", label: "AI ADVISOR", icon: <RobotOutlined /> },
    { id: "pennyscans", label: "PENNY SCANS", icon: <LineChartOutlined /> },
    { id: "institutional", label: "🏛️ INST.", icon: <BarChartOutlined /> },
  ];

  if (isAdminMode) {
    items.push({ id: "learning", label: "🧠 BRAIN", icon: <ExperimentOutlined /> });
    items.push({ id: "alpha", label: "⚡ ALPHA", icon: <ThunderboltOutlined /> });
    items.push({ id: "mindmap", label: "MIND MAP", icon: <PartitionOutlined /> });
    items.push({ id: "admin", label: "ADMIN", icon: <LockOutlined /> });
  }

  const options = items.map((item) => {
    const isActive = activeTab === item.id;
    return {
      label: (
        <span
          className={`flex items-center gap-2 px-3 py-1 font-extrabold tracking-wider text-xs transition-colors duration-200 ${
            isActive ? "text-slate-950" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          {item.icon}
          {item.label}
        </span>
      ),
      value: item.id,
    };
  });

  return (
    <div
      className="mb-8 p-4 md:p-6 rounded-xl border-[1px] border-[#374151] bg-gradient-to-r from-[#111827] via-[#1F2937] to-[#111827]"
      style={{
        backdropFilter: "blur(10px)",
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
      }}
    >
      {/* Mobile view: Swipeable horizontal scroll pill-bar */}
      <div className="flex md:hidden overflow-x-auto whitespace-nowrap gap-2 pb-1 scrollbar-none [mask-image:linear-gradient(to_right,white_85%,transparent_100%)]">
        {items.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id as ModuleTab)}
              className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-extrabold tracking-wider transition-all duration-200 whitespace-nowrap cursor-pointer ${
                isActive
                  ? "bg-[#10B981] text-slate-950 shadow-md shadow-[#10B981]/20 scale-[1.02]"
                  : "bg-slate-800/40 text-slate-400 border border-slate-700/50 hover:text-white"
              }`}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      {/* Desktop view: Standard Segmented Control */}
      <div className="hidden md:block">
        <Segmented
          options={options}
          value={activeTab}
          onChange={(value) => onTabChange(value as ModuleTab)}
          block
          style={{
            backgroundColor: "rgba(55, 65, 81, 0.2)",
            borderRadius: "8px",
            padding: "4px",
          }}
        />
      </div>
    </div>
  );
}
