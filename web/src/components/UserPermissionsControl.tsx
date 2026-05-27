"use client";

import React, { useEffect, useState } from "react";
import {
  Card,
  Form,
  Input,
  Button,
  Table,
  Space,
  Avatar,
  Switch,
  Tooltip,
  message,
  Spin,
  Empty,
} from "antd";
import {
  LockOutlined,
  UserAddOutlined,
  UserOutlined,
  UserSwitchOutlined,
} from "@ant-design/icons";
import {
  adminGetUsers,
  adminCreateUser,
  adminSetPermissions,
  UserRoleProfile,
} from "@/lib/api";

interface PermissionsGridRow {
  key: string;
  email: string;
  avatar: string;
  charts: boolean;
  buys: boolean;
  heatmap: boolean;
  signals: boolean;
  backtest: boolean;
  portfolio: boolean;
  chatbot: boolean;
  actions: string;
}

interface UserPermissionsControlProps {
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

export function UserPermissionsControl({
  onImpersonate,
}: UserPermissionsControlProps) {
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm();
  const [users, setUsers] = useState<UserRoleProfile[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [permissionsLoading, setPermissionsLoading] = useState<string | null>(null);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const response = await adminGetUsers();
      setUsers(response.users || []);
    } catch (error) {
      messageApi.error("Failed to load users");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (values: {
    email: string;
    password: string;
  }) => {
    try {
      setCreating(true);
      await adminCreateUser(values.email, values.password);
      messageApi.success("User created successfully");
      form.resetFields();
      await loadUsers();
    } catch (error: any) {
      messageApi.error(error.message || "Failed to create user");
    } finally {
      setCreating(false);
    }
  };

  const handlePermissionChange = async (
    userId: string,
    feature: string,
    value: boolean
  ) => {
    try {
      setPermissionsLoading(userId);
      const user = users.find((u) => u.id === userId || u.user_id === userId);
      if (!user) throw new Error("User not found");

      const featureMap: Record<string, string> = {
        charts: "can_view_charts",
        buys: "can_view_recommendations",
        heatmap: "can_view_heatmap",
        signals: "can_view_signals",
        backtest: "can_backtest",
        portfolio: "can_use_portfolio",
        chatbot: "can_use_chatbot",
      };

      const apiKey = featureMap[feature];
      if (!apiKey) throw new Error(`Unknown feature: ${feature}`);

      const updatedPermissions = {
        can_view_charts: user.permissions?.can_view_charts || false,
        can_view_recommendations: user.permissions?.can_view_recommendations || false,
        can_view_heatmap: user.permissions?.can_view_heatmap || false,
        can_view_signals: user.permissions?.can_view_signals || false,
        can_backtest: user.permissions?.can_backtest || false,
        can_use_portfolio: user.permissions?.can_use_portfolio || false,
        can_use_chatbot: user.permissions?.can_use_chatbot || false,
        [apiKey]: value,
      };

      await adminSetPermissions(userId, updatedPermissions);
      messageApi.success("Permission updated");
      await loadUsers();
    } catch (error) {
      messageApi.error("Failed to update permission");
    } finally {
      setPermissionsLoading(null);
    }
  };

  const tableData: PermissionsGridRow[] = users.map((user) => ({
    key: user.user_id,
    email: user.email,
    avatar: user.email.charAt(0).toUpperCase(),
    charts: user.permissions?.can_view_charts || false,
    buys: user.permissions?.can_view_recommendations || false,
    heatmap: user.permissions?.can_view_heatmap || false,
    signals: user.permissions?.can_view_signals || false,
    backtest: user.permissions?.can_backtest || false,
    portfolio: user.permissions?.can_use_portfolio || false,
    chatbot: user.permissions?.can_use_chatbot || false,
    actions: user.user_id,
  }));

  const columns = [
    {
      title: "USER",
      dataIndex: "email",
      key: "email",
      width: 250,
      render: (_: string, record: PermissionsGridRow) => (
        <div className="flex items-center gap-3">
          <Avatar
            size={32}
            icon={<UserOutlined />}
            style={{ backgroundColor: "#8B5CF6" }}
          >
            {record.avatar}
          </Avatar>
          <div className="flex flex-col">
            <span className="text-white font-semibold text-sm">{record.email}</span>
            <span className="text-[#6B7280] text-xs">User Account</span>
          </div>
        </div>
      ),
    },
    {
      title: "CHARTS",
      dataIndex: "charts",
      key: "charts",
      align: "center" as const,
      render: (value: boolean, record: PermissionsGridRow) => (
        <Switch
          checked={value}
          onChange={(checked) =>
            handlePermissionChange(record.key, "charts", checked)
          }
          loading={permissionsLoading === record.key}
          style={{
            backgroundColor: value ? "#10B981" : "#6B7280",
          }}
        />
      ),
    },
    {
      title: "BUYS",
      dataIndex: "buys",
      key: "buys",
      align: "center" as const,
      render: (value: boolean, record: PermissionsGridRow) => (
        <Switch
          checked={value}
          onChange={(checked) =>
            handlePermissionChange(record.key, "buys", checked)
          }
          loading={permissionsLoading === record.key}
          style={{
            backgroundColor: value ? "#10B981" : "#6B7280",
          }}
        />
      ),
    },
    {
      title: "HEATMAP",
      dataIndex: "heatmap",
      key: "heatmap",
      align: "center" as const,
      render: (value: boolean, record: PermissionsGridRow) => (
        <Switch
          checked={value}
          onChange={(checked) =>
            handlePermissionChange(record.key, "heatmap", checked)
          }
          loading={permissionsLoading === record.key}
          style={{
            backgroundColor: value ? "#10B981" : "#6B7280",
          }}
        />
      ),
    },
    {
      title: "SIGNALS",
      dataIndex: "signals",
      key: "signals",
      align: "center" as const,
      render: (value: boolean, record: PermissionsGridRow) => (
        <Switch
          checked={value}
          onChange={(checked) =>
            handlePermissionChange(record.key, "signals", checked)
          }
          loading={permissionsLoading === record.key}
          style={{
            backgroundColor: value ? "#10B981" : "#6B7280",
          }}
        />
      ),
    },
    {
      title: "BACKTEST",
      dataIndex: "backtest",
      key: "backtest",
      align: "center" as const,
      render: (value: boolean, record: PermissionsGridRow) => (
        <Switch
          checked={value}
          onChange={(checked) =>
            handlePermissionChange(record.key, "backtest", checked)
          }
          loading={permissionsLoading === record.key}
          style={{
            backgroundColor: value ? "#10B981" : "#6B7280",
          }}
        />
      ),
    },
    {
      title: "PORTFOLIO",
      dataIndex: "portfolio",
      key: "portfolio",
      align: "center" as const,
      render: (value: boolean, record: PermissionsGridRow) => (
        <Switch
          checked={value}
          onChange={(checked) =>
            handlePermissionChange(record.key, "portfolio", checked)
          }
          loading={permissionsLoading === record.key}
          style={{
            backgroundColor: value ? "#10B981" : "#6B7280",
          }}
        />
      ),
    },
    {
      title: "CHATBOT",
      dataIndex: "chatbot",
      key: "chatbot",
      align: "center" as const,
      render: (value: boolean, record: PermissionsGridRow) => (
        <Switch
          checked={value}
          onChange={(checked) =>
            handlePermissionChange(record.key, "chatbot", checked)
          }
          loading={permissionsLoading === record.key}
          style={{
            backgroundColor: value ? "#10B981" : "#6B7280",
          }}
        />
      ),
    },
    {
      title: "ACTION",
      dataIndex: "actions",
      key: "actions",
      width: 120,
      align: "center" as const,
      render: (_: string, record: PermissionsGridRow) => (
        <Tooltip title="Impersonate user">
          <Button
            type="text"
            size="small"
            icon={<UserSwitchOutlined />}
            onClick={() => {
              const permissions = {
                can_view_charts: record.charts,
                can_view_recommendations: record.buys,
                can_view_heatmap: record.heatmap,
                can_view_signals: record.signals,
                can_backtest: record.backtest,
                can_use_portfolio: record.portfolio,
                can_use_chatbot: record.chatbot,
              };
              onImpersonate?.(record.email, record.key, permissions);
            }}
            className="text-[#8B5CF6] hover:text-[#A78BFA]"
          />
        </Tooltip>
      ),
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
          <LockOutlined className="text-[#8B5CF6]" />
          <span className="text-white font-bold text-lg">
            User Permissions Control
          </span>
        </div>
      }
    >
      {/* User Creation Form */}
      <div className="mb-8 p-6 rounded-lg border-[1px] border-[#374151] bg-[#111827]/50">
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <UserAddOutlined className="text-[#10B981]" />
          Register New User
        </h3>
        <Form
          form={form}
          layout="inline"
          onFinish={handleCreateUser}
          className="flex gap-3 flex-wrap"
        >
          <Form.Item
            name="email"
            rules={[
              { required: true, message: "Email required" },
              { type: "email", message: "Invalid email" },
            ]}
            className="mb-0"
          >
            <Input
              placeholder="User Email"
              className="bg-[#1F2937] border-[#374151] text-white rounded-lg w-64"
              style={{
                color: "#F3F4F6",
              }}
            />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: "Password required" }]}
            className="mb-0"
          >
            <Input.Password
              placeholder="User Password"
              className="bg-[#1F2937] border-[#374151] text-white rounded-lg w-64"
              style={{
                color: "#F3F4F6",
              }}
            />
          </Form.Item>
          <Form.Item className="mb-0">
            <Button
              type="primary"
              htmlType="submit"
              loading={creating}
              icon={<UserAddOutlined />}
              className="bg-[#8B5CF6] border-[#8B5CF6] text-white font-semibold hover:bg-[#A78BFA]"
            >
              Register User
            </Button>
          </Form.Item>
        </Form>
      </div>

      {/* Permissions Table */}
      <Spin spinning={loading}>
        {users.length > 0 ? (
          <Table
            columns={columns}
            dataSource={tableData}
            pagination={false}
            rowClassName={() => "!bg-transparent"}
            style={{
              backgroundColor: "transparent",
            }}
          />
        ) : (
          <Empty
            description="No users yet. Create one to get started."
            style={{
              color: "#9CA3AF",
            }}
          />
        )}
      </Spin>
    </Card>
    </>
  );
}
