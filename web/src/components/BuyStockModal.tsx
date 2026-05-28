"use client";

import React, { useState, useEffect } from "react";
import { Modal, InputNumber, Checkbox, Space, Button, message, Alert, Divider, ConfigProvider, theme } from "antd";
import {
  ShoppingOutlined,
  ThunderboltOutlined,
  SafetyCertificateOutlined,
  InfoCircleOutlined,
} from "@ant-design/icons";
import { buyHolding } from "@/lib/api";

interface BuyStockModalProps {
  open: boolean;
  onCancel: () => void;
  onSuccess: () => void;
  symbol: string;
  displaySymbol?: string;
  defaultPrice: number;
  defaultTarget?: number | null;
  defaultStopLoss?: number | null;
  userId: string;
}

export function BuyStockModal({
  open,
  onCancel,
  onSuccess,
  symbol,
  displaySymbol,
  defaultPrice,
  defaultTarget,
  defaultStopLoss,
  userId,
}: BuyStockModalProps) {
  const [loading, setLoading] = useState(false);
  const [qty, setQty] = useState<number>(1);
  const [targetChecked, setTargetChecked] = useState<boolean>(true);
  const [stopChecked, setStopChecked] = useState<boolean>(true);
  const [customTarget, setCustomTarget] = useState<number | null>(null);
  const [customStop, setCustomStop] = useState<number | null>(null);

  const [messageApi, contextHolder] = message.useMessage();

  // Set default values when modal opens
  useEffect(() => {
    if (open) {
      setQty(1);
      setTargetChecked(!!defaultTarget);
      setStopChecked(!!defaultStopLoss);
      setCustomTarget(defaultTarget || null);
      setCustomStop(defaultStopLoss || null);
    }
  }, [open, defaultTarget, defaultStopLoss]);

  const handleBuy = async () => {
    if (qty <= 0) {
      messageApi.error("Quantity must be greater than zero");
      return;
    }
    
    const targetPrice = targetChecked ? customTarget : null;
    const stopLoss = stopChecked ? customStop : null;

    setLoading(true);
    try {
      const res = await buyHolding(userId, symbol, qty, defaultPrice, targetPrice, stopLoss);
      if (res.success) {
        messageApi.success(`Successfully purchased ${qty} share(s) of ${displaySymbol || symbol}!`);
        onSuccess();
      } else {
        messageApi.error("Transaction failed");
      }
    } catch (err: any) {
      messageApi.error(err.message || "Failed to complete transaction");
    } finally {
      setLoading(false);
    }
  };

  const estimatedValue = qty * defaultPrice;

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: "#10B981",
          colorBgBase: "#090d16",
          colorTextBase: "#f3f4f6",
          borderRadius: 12,
        },
      }}
    >
      <Modal
        open={open}
        onCancel={onCancel}
        footer={null}
        centered
        title={
          <div className="flex items-center gap-2 text-white border-b border-slate-800 pb-3">
            <ShoppingOutlined className="text-[#10B981] text-xl" />
            <span className="font-extrabold text-lg">Buy Stock Transaction</span>
          </div>
        }
        className="border border-slate-800 rounded-2xl overflow-hidden shadow-2xl"
        wrapClassName="dark-modal-wrapper"
        styles={{
          body: { backgroundColor: "#090d16", padding: "16px 4px 4px 4px" },
          mask: { backdropFilter: "blur(4px)" }
        }}
        style={{
          borderRadius: "16px",
          overflow: "hidden",
        }}
      >
        {contextHolder}
        <div className="space-y-5 text-slate-300">
          
          {/* Profile Row */}
          <div className="flex justify-between items-center bg-slate-900/40 p-4 rounded-xl border border-slate-800/80 shadow-inner">
            <div>
              <h4 className="text-white text-lg font-black tracking-tight">{displaySymbol || symbol}</h4>
              <p className="text-[#9CA3AF] text-[10px] font-bold uppercase tracking-wider">Live Price</p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-black text-emerald-400">₹{defaultPrice.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
            </div>
          </div>

          {/* Quantity Select */}
          <div className="space-y-2">
            <label className="block text-slate-400 text-xs font-semibold uppercase tracking-wider">Shares Quantity to Buy</label>
            <InputNumber
              min={1}
              precision={0}
              value={qty}
              onChange={(val) => setQty(val || 1)}
              className="w-full font-bold"
              size="large"
              style={{
                height: "42px",
                lineHeight: "42px",
                fontSize: "16px",
              }}
            />
          </div>

          {/* Triggers Selection */}
          <div className="p-4 rounded-xl bg-slate-900/20 border border-slate-800/60 space-y-4">
            <div className="flex items-center justify-between">
              <h5 className="text-white font-bold text-xs uppercase flex items-center gap-1.5">
                <ThunderboltOutlined className="text-amber-500" />
                Auto-Execute Triggers
              </h5>
              <span className="text-[9px] text-emerald-400 font-extrabold bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-500/20">
                System Recommended pre-filled
              </span>
            </div>

            <Divider className="!m-0 !border-slate-800/60" />

            {/* Target Price */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <Checkbox
                checked={targetChecked}
                onChange={(e) => setTargetChecked(e.target.checked)}
                className="!text-slate-200 font-semibold text-xs"
              >
                📊 Target Price Auto-Sell
              </Checkbox>
              <InputNumber
                disabled={!targetChecked}
                min={0}
                value={customTarget}
                onChange={(val) => setCustomTarget(val)}
                formatter={(value) => `₹ ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}
                parser={(value) => value ? parseFloat(value.replace(/₹\s?|(,*)/g, "")) : 0}
                className="w-full sm:w-36 font-semibold"
              />
            </div>

            {/* Stop Loss */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <Checkbox
                checked={stopChecked}
                onChange={(e) => setStopChecked(e.target.checked)}
                className="!text-slate-200 font-semibold text-xs"
              >
                🛡️ Stop Loss Auto-Sell
              </Checkbox>
              <InputNumber
                disabled={!stopChecked}
                min={0}
                value={customStop}
                onChange={(val) => setCustomStop(val)}
                formatter={(value) => `₹ ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}
                parser={(value) => value ? parseFloat(value.replace(/₹\s?|(,*)/g, "")) : 0}
                className="w-full sm:w-36 font-semibold"
              />
            </div>

            {targetChecked || stopChecked ? (
              <div className="flex items-start gap-2 p-2 rounded bg-amber-500/5 border border-amber-500/10 text-xxs text-amber-300 leading-normal">
                <InfoCircleOutlined className="text-amber-500 mt-0.5" />
                <span>
                  Your position will automatically close and lock realized profit/loss inside the Passbook if the stock hits these prices.
                </span>
              </div>
            ) : null}
          </div>

          {/* Investment Details Summary */}
          <div className="flex justify-between items-center p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-sm">
            <span className="text-slate-500 font-bold uppercase text-[10px] tracking-wider">Estimated Investment</span>
            <span className="text-lg font-black text-white">₹{estimatedValue.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
          </div>

          {/* Buttons */}
          <div className="flex gap-3 pt-3">
            <Button
              onClick={onCancel}
              className="flex-1 !bg-slate-900/40 !border-slate-800 !text-slate-400 hover:!text-white hover:!bg-slate-800/40 hover:!border-slate-700 transition-all duration-200"
              size="large"
            >
              Cancel
            </Button>
            <Button
              type="primary"
              onClick={handleBuy}
              loading={loading}
              className="flex-1 !bg-gradient-to-r !from-emerald-500 !to-teal-600 hover:!from-emerald-400 hover:!to-teal-500 !border-none !font-black !text-white tracking-wide shadow-lg hover:shadow-emerald-500/20 transition-all duration-200"
              size="large"
            >
              CONFIRM BUY 🛒
            </Button>
          </div>

        </div>
      </Modal>
    </ConfigProvider>
  );
}
