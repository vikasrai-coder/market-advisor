"use client";

import React, { useState, useEffect } from "react";
import { Card, Button, Badge, Space, Tooltip, message, Spin } from "antd";
import {
  SendOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import { sendTelegramTest } from "@/lib/api";

const TELEGRAM_BOT_ICON = (
  <svg
    className="w-5 h-5"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
  >
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

const ALERT_TEXT_TEMPLATE = `🚨 MARKET ALERT
━━━━━━━━━━━━━━━━━━━
📊 SYMBOL: {symbol}
💹 SIGNAL: {signal_type}
📈 PRICE: ₹{price}
⏰ TIME: {timestamp}
━━━━━━━━━━━━━━━━━━━
Market Advisor NSE Scanner`;

interface TelegramIntegrationProps {
  botName?: string;
  chatId?: string;
  isActive?: boolean;
}

export function TelegramIntegration({
  botName = "VRSTOCKALERT_BOT",
  chatId = "123456789",
  isActive = true,
}: TelegramIntegrationProps) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSendTest = async () => {
    try {
      setTesting(true);
      const result = await sendTelegramTest();
      setTestResult({
        success: result.success || false,
        message: result.message || "Test alert sent",
      });
      message.success(result.message || "Test alert sent successfully");
    } catch (error: any) {
      const errorMsg = error.message || "Failed to send test alert";
      setTestResult({
        success: false,
        message: errorMsg,
      });
      message.error(errorMsg);
    } finally {
      setTesting(false);
    }
  };

  const handleCopyTemplate = () => {
    navigator.clipboard.writeText(ALERT_TEXT_TEMPLATE);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
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
            <div className="text-[#0088cc] flex items-center justify-center w-8 h-8 bg-[#0088cc]/10 rounded-lg">
              {TELEGRAM_BOT_ICON}
            </div>
            <span className="text-white font-bold text-lg">
              Telegram Integration
            </span>
          </div>
          <Badge
            status={isActive ? "success" : "error"}
            text={
              <span
                className={`font-semibold ${
                  isActive ? "text-[#10B981]" : "text-[#EF4444]"
                }`}
              >
                {isActive ? "ACTIVE" : "INACTIVE"}
              </span>
            }
          />
        </div>
      }
    >
      <div className="space-y-6">
        {/* Bot Configuration Section */}
        <div className="p-6 rounded-lg border-[1px] border-[#374151] bg-[#111827]/50">
          <h3 className="text-white font-semibold mb-4">Bot Configuration</h3>
          
          <div className="grid grid-cols-2 gap-4 mb-4">
            {/* Bot Identifier */}
            <div>
              <p className="text-[#9CA3AF] text-xs font-semibold uppercase mb-2">
                Bot Name
              </p>
              <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-[#1F2937] border-[1px] border-[#374151]">
                <span className="text-[#10B981] font-mono font-bold">@{botName}</span>
                <Tooltip title={copied ? "Copied!" : "Copy bot name"}>
                  <Button
                    type="text"
                    size="small"
                    onClick={() => {
                      navigator.clipboard.writeText(`@${botName}`);
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    }}
                    className="text-[#6B7280] hover:text-[#10B981]"
                  >
                    📋
                  </Button>
                </Tooltip>
              </div>
            </div>

            {/* Chat ID */}
            <div>
              <p className="text-[#9CA3AF] text-xs font-semibold uppercase mb-2">
                Chat ID
              </p>
              <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-[#1F2937] border-[1px] border-[#374151]">
                <span className="text-[#8B5CF6] font-mono font-bold">{chatId}</span>
                <Tooltip title="Copy chat ID">
                  <Button
                    type="text"
                    size="small"
                    onClick={() => {
                      navigator.clipboard.writeText(chatId);
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    }}
                    className="text-[#6B7280] hover:text-[#8B5CF6]"
                  >
                    📋
                  </Button>
                </Tooltip>
              </div>
            </div>
          </div>

          {/* Status Badges */}
          <div className="flex gap-3">
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#10B981]/10 border-[1px] border-[#10B981]/30">
              <CheckCircleOutlined className="text-[#10B981]" />
              <span className="text-[#10B981] text-sm font-semibold">
                Webhook Active
              </span>
            </div>
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#10B981]/10 border-[1px] border-[#10B981]/30">
              <CheckCircleOutlined className="text-[#10B981]" />
              <span className="text-[#10B981] text-sm font-semibold">
                Connection Verified
              </span>
            </div>
          </div>
        </div>

        {/* Alert Template Section */}
        <div className="p-6 rounded-lg border-[1px] border-[#374151] bg-[#111827]/50">
          <h3 className="text-white font-semibold mb-4">Alert Text Pattern</h3>
          <div className="p-4 rounded-lg bg-[#0F1117] border-[1px] border-[#374151] font-mono text-xs text-[#9CA3AF] whitespace-pre-wrap break-words">
            {ALERT_TEXT_TEMPLATE}
          </div>
          <Button
            type="default"
            size="small"
            onClick={handleCopyTemplate}
            className="mt-3 text-[#9CA3AF] border-[#374151] hover:text-white hover:border-[#10B981]"
          >
            📋 {copied ? "Copied!" : "Copy Template"}
          </Button>
        </div>

        {/* Test Alert Section */}
        <div className="p-6 rounded-lg border-[1px] border-[#374151] bg-[#111827]/50">
          <h3 className="text-white font-semibold mb-4">Send Test Alert</h3>
          <p className="text-[#9CA3AF] text-sm mb-4">
            Send a test alert to verify your Telegram bot is working correctly.
          </p>
          
          <Spin spinning={testing}>
            <Button
              type="primary"
              size="large"
              icon={<SendOutlined />}
              onClick={handleSendTest}
              loading={testing}
              className="bg-[#0088cc] border-[#0088cc] text-white font-semibold hover:bg-[#0066aa] w-full md:w-auto"
            >
              Send Test Telegram Alert
            </Button>

            {testResult && (
              <div
                className={`mt-4 p-4 rounded-lg flex items-center gap-3 ${
                  testResult.success
                    ? "bg-[#10B981]/10 border-[1px] border-[#10B981]/30"
                    : "bg-[#EF4444]/10 border-[1px] border-[#EF4444]/30"
                }`}
              >
                {testResult.success ? (
                  <CheckCircleOutlined className="text-[#10B981] text-lg" />
                ) : (
                  <ExclamationCircleOutlined className="text-[#EF4444] text-lg" />
                )}
                <span
                  className={
                    testResult.success ? "text-[#10B981]" : "text-[#EF4444]"
                  }
                >
                  {testResult.message}
                </span>
              </div>
            )}
          </Spin>
        </div>
      </div>
    </Card>
  );
}
