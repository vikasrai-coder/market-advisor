"use client";

import React from "react";
import { Layout, Space, ConfigProvider, theme } from "antd";
import { UserPermissionsControl } from "./UserPermissionsControl";
import { SystemSettingsControl } from "./SystemSettingsControl";
import { PrivateTradingCard } from "./PrivateTradingCard";
import { TelegramIntegration } from "./TelegramIntegration";

interface AdminDashboardProps {
  onImpersonate?: (
    userEmail: string,
    userId: string,
    permissions: {
      can_view_charts: boolean;
      can_view_recommendations: boolean;
      can_view_heatmap: boolean;
      can_view_signals: boolean;
      can_backtest: boolean;
      can_use_portfolio: boolean;
      can_use_chatbot: boolean;
    }
  ) => void;
}

export default function AdminDashboard({ onImpersonate }: AdminDashboardProps) {
  const handleImpersonate = (
    userEmail: string,
    userId: string,
    permissions: {
      can_view_charts: boolean;
      can_view_recommendations: boolean;
      can_view_heatmap: boolean;
      can_view_signals: boolean;
      can_backtest: boolean;
      can_use_portfolio: boolean;
      can_use_chatbot: boolean;
    }
  ) => {
    onImpersonate?.(userEmail, userId, permissions);
  };

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorBgContainer: "transparent",
        },
      }}
    >
      <Layout
        style={{
          backgroundColor: "transparent",
        }}
      >
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          {/* User Permissions Control Center */}
          <UserPermissionsControl onImpersonate={handleImpersonate} />

          {/* Resource Usage & System Optimization Switch */}
          <SystemSettingsControl />

          {/* Private Trading Dashboard */}
          <PrivateTradingCard symbols={[
            "INFY",
            "TCS",
            "RELIANCE",
            "BAJAJ-AUTO",
            "HDFC",
            "ICICIBANK",
            "HINDUNILVR",
            "LT",
            "MARUTI",
            "WIPRO",
          ]} />

          {/* Telegram Integration Suite */}
          <TelegramIntegration 
            botName="VRSTOCKALERT_BOT"
            chatId="123456789"
            isActive={true}
          />
        </Space>
      </Layout>
    </ConfigProvider>
  );
}


