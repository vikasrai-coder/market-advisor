"use client";

import React, { useState, useEffect } from "react";
import { Card, Button, Badge, Space, Tooltip, message, Spin, Switch, Radio } from "antd";
import {
  SlidersOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
} from "@ant-design/icons";
import { adminGetSystemSettings, adminSaveSystemSettings, SystemSettings } from "@/lib/api";

const SYSTEM_SETTINGS_ICON = (
  <svg
    className="w-5 h-5"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
  >
    <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.1a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

export function SystemSettingsControl() {
  const [messageApi, contextHolder] = message.useMessage();
  const [loading, setLoading] = useState(false);
  const [settings, setSettings] = useState<SystemSettings | null>(null);

  // Future Priorities State Mock
  const [futurePriority, setFuturePriority] = useState<string>("default");
  const [futureEnvironment, setFutureEnvironment] = useState<string>("production");

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await adminGetSystemSettings();
      setSettings(data);
    } catch (err: any) {
      messageApi.error(err.message || "Failed to load system settings");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleMode = async (mode: "low" | "high") => {
    try {
      setLoading(true);
      const res = await adminSaveSystemSettings(mode);
      if (res.success) {
        setSettings(res.settings);
        if (mode === "low") {
          messageApi.success("Switched to LOW USAGE mode — optimized for Vercel Fluid CPU limit.");
        } else {
          messageApi.warning("Switched to HIGH USAGE mode — fully detailed AI insights enabled.");
        }
      }
    } catch (err: any) {
      messageApi.error(err.message || "Failed to update system settings");
    } finally {
      setLoading(false);
    }
  };

  const currentMode = settings?.usage_mode || "low";

  return (
    <>
      {contextHolder}
      <Card
        className="border-[1px] border-[#374151] bg-gradient-to-br from-[#111827] via-[#1F2937] to-[#111827] rounded-xl"
        style={{
          background: "transparent",
          backdropFilter: "blur(10px)",
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
        }}
        title={
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-3">
              <div className="text-[#3B82F6] flex items-center justify-center w-8 h-8 bg-[#3B82F6]/10 rounded-lg">
                {SYSTEM_SETTINGS_ICON}
              </div>
              <span className="text-white font-bold text-lg">
                Resource Usage & System Optimization
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Badge
                status={currentMode === "low" ? "success" : "warning"}
                text={
                  <span
                    className={`font-semibold flex items-center gap-1.5 ${
                      currentMode === "low" ? "text-[#10B981]" : "text-[#F59E0B]"
                    }`}
                  >
                    <span className={`inline-block w-2.5 h-2.5 rounded-full ${
                      currentMode === "low" 
                        ? "bg-[#10B981] animate-pulse shadow-[0_0_8px_#10B981]" 
                        : "bg-[#F59E0B] animate-pulse shadow-[0_0_8px_#F59E0B]"
                    }`} />
                    {currentMode === "low" ? "LOW USAGE (SAFE)" : "HIGH USAGE (INTENSE)"}
                  </span>
                }
              />
            </div>
          </div>
        }
      >
        <Spin spinning={loading} tip="Syncing settings...">
          <div className="space-y-6">
            
            {/* Core Usage Control Card */}
            <div className="p-6 rounded-lg border-[1px] border-[#374151] bg-[#111827]/50">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div className="max-w-xl">
                  <h3 className="text-white font-semibold text-base mb-2">Active Processing Mode</h3>
                  <p className="text-[#9CA3AF] text-sm leading-relaxed">
                    Optimize CPU execution runtimes to prevent Vercel Serverless limits exhaustion. 
                    <strong> Low Usage mode</strong> completes scans in under 3 seconds (recommending 95%+ CPU cost savings).
                  </p>
                </div>
                
                <div className="flex flex-col items-start md:items-end gap-2">
                  <span className="text-[#9CA3AF] text-xs font-semibold uppercase tracking-wider">
                    Select Mode
                  </span>
                  <Radio.Group
                    value={currentMode}
                    onChange={(e) => handleToggleMode(e.target.value)}
                    buttonStyle="solid"
                    className="p-1 rounded-lg bg-[#1F2937] border-[1px] border-[#374151]"
                  >
                    <Radio.Button 
                      value="low"
                      className={`font-semibold transition-all duration-300 ${
                        currentMode === "low" 
                          ? "!bg-[#10B981] !text-black !border-[#10B981]" 
                          : "!bg-transparent !text-[#9CA3AF] !border-transparent hover:!text-white"
                      }`}
                    >
                      🍃 Low Usage (Default)
                    </Radio.Button>
                    <Radio.Button 
                      value="high"
                      className={`font-semibold transition-all duration-300 ${
                        currentMode === "high" 
                          ? "!bg-[#F59E0B] !text-black !border-[#F59E0B]" 
                          : "!bg-transparent !text-[#9CA3AF] !border-transparent hover:!text-white"
                      }`}
                    >
                      ⚡ High Usage
                    </Radio.Button>
                  </Radio.Group>
                </div>
              </div>

              {/* Mode specifications details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
                {/* Low Usage Card details */}
                <div className={`p-4 rounded-lg border-[1px] transition-colors ${
                  currentMode === "low" 
                    ? "border-[#10B981]/40 bg-[#10B981]/5" 
                    : "border-[#374151] bg-[#111827]/30"
                }`}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">🍃</span>
                    <h4 className="text-white font-semibold text-sm">Low Usage Specifications</h4>
                  </div>
                  <ul className="text-[#9CA3AF] text-xs space-y-1.5 list-disc pl-4">
                    <li>Execution Time: <span className="text-[#10B981] font-semibold">&lt; 3.0 seconds</span></li>
                    <li>Vercel Fluid CPU Consumed: <span className="text-[#10B981] font-semibold">Minimal (~0.001 Hrs)</span></li>
                    <li>Pipeline: Uses pure rule-based scanning logic and technical thresholds</li>
                    <li>Excludes: Slow FinBERT news sentiment fetches and LLM summaries</li>
                    <li>Status: <span className="text-[#10B981] font-semibold">Highly recommended for intraday crons</span></li>
                  </ul>
                </div>

                {/* High Usage Card details */}
                <div className={`p-4 rounded-lg border-[1px] transition-colors ${
                  currentMode === "high" 
                    ? "border-[#F59E0B]/40 bg-[#F59E0B]/5" 
                    : "border-[#374151] bg-[#111827]/30"
                }`}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">⚡</span>
                    <h4 className="text-white font-semibold text-sm">High Usage Specifications</h4>
                  </div>
                  <ul className="text-[#9CA3AF] text-xs space-y-1.5 list-disc pl-4">
                    <li>Execution Time: <span className="text-[#F59E0B] font-semibold">~60.0 - 90.0 seconds</span></li>
                    <li>Vercel Fluid CPU Consumed: <span className="text-[#EF4444] font-semibold">High (~0.025 Hrs)</span></li>
                    <li>Pipeline: Runs heavy news sentiment indexation and real-time scrapes</li>
                    <li>Includes: HuggingFace text-classification + LLM model summaries</li>
                    <li>Status: <span className="text-[#F59E0B] font-semibold">Use sparingly to protect serverless active CPU</span></li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Environment Variable Overrides & Future Priorities */}
            <div className="p-6 rounded-lg border-[1px] border-[#374151] bg-[#111827]/50">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <SlidersOutlined className="text-[#8B5CF6]" />
                  <h3 className="text-white font-semibold">Environment & Instance Priorities</h3>
                </div>
                <Badge count="Future Planned" className="bg-[#8B5CF6]/20 border-[1px] border-[#8B5CF6]/50 text-[#C084FC] text-[10px] px-2 py-0.5 rounded font-mono font-semibold" />
              </div>
              <p className="text-[#9CA3AF] text-sm mb-4 leading-relaxed">
                Configure separate overrides dynamically depending on where the instance is running. 
                For example, if running in a high-priority production system, keep processing settings set to High Usage automatically, 
                while staging and local developer boxes stay clamped to Low Usage.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4 opacity-60 pointer-events-none select-none">
                <div>
                  <label className="block text-[#9CA3AF] text-xs font-semibold uppercase mb-2">
                    Target Instance Environment
                  </label>
                  <Radio.Group
                    value={futureEnvironment}
                    onChange={(e) => setFutureEnvironment(e.target.value)}
                    className="w-full grid grid-cols-3 gap-2"
                  >
                    <Radio.Button value="local" className="!bg-[#1F2937] !text-[#9CA3AF] !border-[#374151] text-center">Local</Radio.Button>
                    <Radio.Button value="staging" className="!bg-[#1F2937] !text-[#9CA3AF] !border-[#374151] text-center">Staging</Radio.Button>
                    <Radio.Button value="production" className="!bg-[#1F2937] !text-[#9CA3AF] !border-[#374151] text-center">Production</Radio.Button>
                  </Radio.Group>
                </div>

                <div>
                  <label className="block text-[#9CA3AF] text-xs font-semibold uppercase mb-2">
                    Priority Rules Overrides
                  </label>
                  <Radio.Group
                    value={futurePriority}
                    onChange={(e) => setFuturePriority(e.target.value)}
                    className="w-full grid grid-cols-2 gap-2"
                  >
                    <Radio.Button value="default" className="!bg-[#1F2937] !text-[#9CA3AF] !border-[#374151] text-center">Use Global Switch</Radio.Button>
                    <Radio.Button value="force_high" className="!bg-[#1F2937] !text-[#9CA3AF] !border-[#374151] text-center">Force High Usage</Radio.Button>
                  </Radio.Group>
                </div>
              </div>

              <div className="mt-4 flex items-center gap-2 p-3 rounded bg-[#8B5CF6]/5 border-[1px] border-[#8B5CF6]/20">
                <InfoCircleOutlined className="text-[#8B5CF6] text-sm" />
                <span className="text-[#C084FC] text-xs">
                  In future, these local environment priorities will be injected automatically through environment variables (e.g. <code>INSTANCE_PRIORITY=high</code>).
                </span>
              </div>
            </div>

          </div>
        </Spin>
      </Card>
    </>
  );
}
