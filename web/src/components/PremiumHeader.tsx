"use client";

import React from "react";
import { Layout, Button, Avatar, Dropdown, Space } from "antd";
import {
  LogoutOutlined,
  UserOutlined,
  BellOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

interface PremiumHeaderProps {
  userEmail?: string;
  userName?: string;
  onSignOut?: () => void;
}

export function PremiumHeader({
  userEmail = "vikas.raiexp@gmail.com",
  userName = "Vikas",
  onSignOut,
}: PremiumHeaderProps) {
  const router = useRouter();

  const handleSignOut = async () => {
    try {
      const supabase = createClient();
      await supabase.auth.signOut();
      localStorage.removeItem("offline_user_id");
      localStorage.removeItem("offline_user_email");
      localStorage.removeItem("offline_user_role");
      router.push("/login");
      onSignOut?.();
    } catch (error) {
      console.error("Sign out error:", error);
    }
  };

  const userMenuItems = [
    {
      key: "profile",
      label: "Profile",
      icon: <UserOutlined />,
    },
    {
      key: "settings",
      label: "Settings",
      icon: <SettingOutlined />,
    },
    {
      type: "divider" as const,
    },
    {
      key: "logout",
      label: "Sign Out",
      icon: <LogoutOutlined />,
      danger: true,
      onClick: handleSignOut,
    },
  ];

  return (
    <Layout.Header
      className="sticky top-0 z-50 backdrop-blur-md bg-gradient-to-r from-[rgba(11,15,25,0.95)] via-[rgba(17,24,39,0.95)] to-[rgba(11,15,25,0.95)]"
      style={{
        borderBottom: "1px solid rgba(55, 65, 81, 0.5)",
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
        height: "72px",
        paddingInline: "48px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      {/* Logo & Branding */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-gradient-to-br from-[#10B981] to-[#059669] rounded-lg flex items-center justify-center">
          <span className="text-white font-bold text-lg">MA</span>
        </div>
        <div className="flex flex-col">
          <span className="text-white font-bold text-lg leading-tight">
            Market Advisor
          </span>
          <span className="text-[#9CA3AF] text-xs font-medium">
            NSE Stock Intelligence
          </span>
        </div>
      </div>

      {/* Right Section - User Profile & Actions */}
      <div className="flex items-center gap-6">
        {/* Notification Bell */}
        <Button
          type="text"
          icon={<BellOutlined className="text-[#D1D5DB] text-lg" />}
          size="large"
          className="hover:bg-white/10 rounded-lg"
        />

        {/* User Profile Dropdown */}
        <Dropdown menu={{ items: userMenuItems }}>
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/10 cursor-pointer transition">
            <Avatar
              size={40}
              icon={<UserOutlined />}
              style={{ backgroundColor: "#8B5CF6" }}
            />
            <div className="flex flex-col">
              <span className="text-white font-semibold text-sm leading-tight">
                {userName}
              </span>
              <span className="text-[#9CA3AF] text-xs font-normal">
                {userEmail}
              </span>
            </div>
          </div>
        </Dropdown>
      </div>
    </Layout.Header>
  );
}
