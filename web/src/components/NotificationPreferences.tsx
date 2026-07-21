"use client";

import React, { useEffect, useState } from "react";
import { Card, Input, Switch, Button, message, ConfigProvider, theme } from "antd";
import { BellOutlined, SendOutlined, CheckCircleOutlined } from "@ant-design/icons";
import {
  getUserNotificationPreferences,
  saveUserNotificationPreferences,
  type UserNotificationPreferences,
} from "@/lib/api";

export default function NotificationPreferences({ userId }: { userId: string }) {
  const [messageApi, contextHolder] = message.useMessage();
  const [chatId, setChatId] = useState("");
  const [targetHit, setTargetHit] = useState(true);
  const [stoppedOut, setStoppedOut] = useState(true);
  const [bearishWarning, setBearishWarning] = useState(true);
  const [newSignal, setNewSignal] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!userId) return;
    getUserNotificationPreferences(userId)
      .then((prefs) => {
        setChatId(prefs.telegram_chat_id || "");
        setTargetHit(prefs.notify_target_hit);
        setStoppedOut(prefs.notify_stopped_out);
        setBearishWarning(prefs.notify_bearish_warning);
        setNewSignal(prefs.notify_new_signal);
      })
      .catch(() => {});
  }, [userId]);

  const handleSave = async () => {
    setLoading(true);
    try {
      await saveUserNotificationPreferences({
        user_id: userId,
        telegram_chat_id: chatId.trim() || null,
        notify_target_hit: targetHit,
        notify_stopped_out: stoppedOut,
        notify_bearish_warning: bearishWarning,
        notify_new_signal: newSignal,
        notify_modes: ["swing", "intraday"],
      });
      messageApi.success("Personal notification preferences saved!");
    } catch (err: any) {
      messageApi.error(err.message || "Failed to save preferences");
    } finally {
      setLoading(false);
    }
  };

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
      <Card
        className={cardClass}
        style={cardStyle}
        title={
          <div className="flex items-center gap-2">
            <BellOutlined className="text-cyan-400" />
            <span className="text-slate-200 font-bold">Personal Telegram Alerts & Notification Preferences</span>
          </div>
        }
      >
        <div className="space-y-4 text-xs">
          <div>
            <label className="text-slate-400 font-semibold mb-1 block">Your Telegram Chat ID</label>
            <Input
              placeholder="e.g. 123456789 (leave empty to use global channel)"
              value={chatId}
              onChange={(e) => setChatId(e.target.value)}
              className="!bg-slate-900 !border-slate-800 !text-slate-200"
              prefix={<SendOutlined className="text-slate-500" />}
            />
            <p className="text-[10px] text-slate-500 mt-1">
              Start a chat with your bot and send <code>/start</code> to get your Chat ID.
            </p>
          </div>

          <div className="space-y-3 pt-2 border-t border-slate-800">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-slate-200 font-semibold block">🎯 Target Price Hit Alerts</span>
                <span className="text-slate-500 text-[10px]">Receive instant notification when target price is hit</span>
              </div>
              <Switch checked={targetHit} onChange={setTargetHit} />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <span className="text-slate-200 font-semibold block">🛡️ Stop Loss Trigger Alerts</span>
                <span className="text-slate-500 text-[10px]">Receive notification when a stop loss level is breached</span>
              </div>
              <Switch checked={stoppedOut} onChange={setStoppedOut} />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <span className="text-slate-200 font-semibold block">⚠️ Bearish Structural Warnings</span>
                <span className="text-slate-500 text-[10px]">Early warnings when momentum deteriorates before stop loss</span>
              </div>
              <Switch checked={bearishWarning} onChange={setBearishWarning} />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <span className="text-slate-200 font-semibold block">⚡ New High-Conviction Signals</span>
                <span className="text-slate-500 text-[10px]">Notify whenever a new S-Tier recommendation is generated</span>
              </div>
              <Switch checked={newSignal} onChange={setNewSignal} />
            </div>
          </div>

          <div className="pt-2 flex justify-end">
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={handleSave}
              loading={loading}
              className="!bg-emerald-600 hover:!bg-emerald-500 !border-emerald-500"
            >
              Save Preferences
            </Button>
          </div>
        </div>
      </Card>
    </ConfigProvider>
  );
}
