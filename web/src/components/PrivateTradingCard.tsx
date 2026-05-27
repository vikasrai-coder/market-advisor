"use client";

import React, { useEffect, useState } from "react";
import {
  Card,
  Row,
  Col,
  Form,
  Input,
  Button,
  Table,
  Empty,
  message,
  Select,
  Spin,
} from "antd";
import {
  ShoppingOutlined,
  DollarOutlined,
  PlusOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import {
  adminGetTrades,
  adminBuyTrade,
  adminSellTrade,
  AdminTrade,
} from "@/lib/api";

interface PrivateTradingCardProps {
  symbols?: string[];
}

const POPULAR_SYMBOLS = [
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
];

export function PrivateTradingCard({
  symbols = POPULAR_SYMBOLS,
}: PrivateTradingCardProps) {
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm();
  const [trades, setTrades] = useState<AdminTrade[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [closingTradeId, setClosingTradeId] = useState<string | null>(null);

  useEffect(() => {
    loadTrades();
  }, []);

  const loadTrades = async () => {
    try {
      setLoading(true);
      const response = await adminGetTrades();
      setTrades(response.trades || []);
    } catch (error) {
      messageApi.error("Failed to load trades");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleRecordTrade = async (values: {
    symbol: string;
    qty: number;
    buyPrice: number;
  }) => {
    try {
      setCreating(true);
      await adminBuyTrade(values.symbol, values.qty, values.buyPrice);
      messageApi.success("Trade recorded successfully");
      form.resetFields();
      await loadTrades();
    } catch (error: any) {
      messageApi.error(error.message || "Failed to record trade");
    } finally {
      setCreating(false);
    }
  };

  const handleCloseTrade = async (tradeId: string, sellPrice: number) => {
    if (sellPrice <= 0) {
      messageApi.error("Please enter a valid sell price");
      return;
    }
    try {
      setClosingTradeId(tradeId);
      await adminSellTrade(tradeId, sellPrice);
      messageApi.success("Trade closed successfully");
      await loadTrades();
    } catch (error: any) {
      messageApi.error(error.message || "Failed to close trade");
    } finally {
      setClosingTradeId(null);
    }
  };

  const columns = [
    {
      title: "SYMBOL",
      dataIndex: "symbol",
      key: "symbol",
      render: (text: string) => (
        <span className="text-white font-semibold">{text}</span>
      ),
    },
    {
      title: "QTY",
      dataIndex: "qty",
      key: "qty",
      render: (text: number) => (
        <span className="text-[#9CA3AF]">{text} shares</span>
      ),
    },
    {
      title: "BUY PRICE",
      dataIndex: "buy_price",
      key: "buy_price",
      render: (price: number) => (
        <span className="text-[#10B981]">₹{price.toFixed(2)}</span>
      ),
    },
    {
      title: "CURRENT VALUE",
      dataIndex: "current_value",
      key: "current_value",
      render: (value: number) => (
        <span className="text-[#F59E0B]">₹{value.toFixed(2)}</span>
      ),
    },
    {
      title: "STATUS",
      dataIndex: "trade_status",
      key: "trade_status",
      render: (status: string) => (
        <span
          className={`px-3 py-1 rounded-full text-xs font-semibold ${
            status === "open"
              ? "bg-[#10B981]/20 text-[#10B981]"
              : "bg-[#EF4444]/20 text-[#EF4444]"
          }`}
        >
          {status === "open" ? "OPEN" : "CLOSED"}
        </span>
      ),
    },
    {
      title: "ACTION",
      key: "action",
      render: (_: any, record: AdminTrade) =>
        record.trade_status === "open" ? (
          <Button
            type="text"
            danger
            size="small"
            icon={<DeleteOutlined />}
            onClick={() => {
              const sellPrice = prompt("Enter sell price:");
              if (sellPrice) {
                handleCloseTrade(record.id || "", parseFloat(sellPrice));
              }
            }}
            loading={closingTradeId === record.id}
            className="text-[#EF4444]"
          >
            Close
          </Button>
        ) : null,
    },
  ];

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

        <div className="flex items-center gap-2">
          <ShoppingOutlined className="text-[#10B981]" />
          <span className="text-white font-bold text-lg">
            Admin Private Trading
          </span>
        </div>
      }
    >
      <Row gutter={24}>
        {/* Left Side - Form */}
        <Col xs={24} md={12}>
          <div className="p-6 rounded-lg border-[1px] border-[#374151] bg-[#111827]/50">
            <h3 className="text-white font-semibold mb-4">Record Private Trade</h3>
            <Form
              form={form}
              layout="vertical"
              onFinish={handleRecordTrade}
            >
              <Form.Item
                name="symbol"
                label={<span className="text-[#9CA3AF] font-semibold">Stock Symbol</span>}
                rules={[{ required: true, message: "Please select a symbol" }]}
              >
                <Select
                  placeholder="Select or type symbol..."
                  className="bg-[#1F2937] border-[#374151] rounded-lg"
                  options={symbols.map((s) => ({ label: s, value: s }))}
                />
              </Form.Item>

              <Form.Item
                name="qty"
                label={<span className="text-[#9CA3AF] font-semibold">Quantity</span>}
                rules={[
                  { required: true, message: "Quantity required" },
                  { type: "number", min: 1, message: "Must be >= 1" },
                ]}
              >
                <Input
                  type="number"
                  placeholder="Number of shares"
                  className="bg-[#1F2937] border-[#374151] text-white rounded-lg"
                  min={1}
                />
              </Form.Item>

              <Form.Item
                name="buyPrice"
                label={<span className="text-[#9CA3AF] font-semibold">Buy Price (₹)</span>}
                rules={[
                  { required: true, message: "Buy price required" },
                  { type: "number", min: 0.01, message: "Must be > 0" },
                ]}
              >
                <Input
                  type="number"
                  placeholder="0.00"
                  prefix={<DollarOutlined className="text-[#10B981]" />}
                  className="bg-[#1F2937] border-[#374151] text-white rounded-lg"
                  step={0.01}
                />
              </Form.Item>

              <Form.Item className="mb-0">
                <Button
                  type="primary"
                  htmlType="submit"
                  block
                  loading={creating}
                  icon={<PlusOutlined />}
                  className="bg-[#10B981] border-[#10B981] text-white font-semibold hover:bg-[#059669] h-10"
                >
                  Record Trade
                </Button>
              </Form.Item>
            </Form>
          </div>
        </Col>

        {/* Right Side - Positions Table */}
        <Col xs={24} md={12}>
          <div className="p-6 rounded-lg border-[1px] border-[#374151] bg-[#111827]/50">
            <h3 className="text-white font-semibold mb-4">Active Book Positions</h3>
            <Spin spinning={loading}>
              {trades.length > 0 ? (
                <Table
                  columns={columns}
                  dataSource={trades}
                  pagination={false}
                  rowClassName={() => "!bg-transparent"}
                  size="small"
                />
              ) : (
                <Empty
                  description="No private trades recorded yet."
                  style={{
                    color: "#9CA3AF",
                  }}
                />
              )}
            </Spin>
          </div>
        </Col>
      </Row>
    </Card>
    </>
  );
}
