"use client";

import React from "react";
import { Layout, Button, Avatar, Dropdown, ConfigProvider, theme } from "antd";
import {
  LogoutOutlined,
  UserOutlined,
  BellOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export function AuthHeader({
  email = "vikas.raiexp@gmail.com",
}: {
  email?: string | null;
}) {
  const router = useRouter();
  const pathname = usePathname();

  const handleSignOut = async () => {
    try {
      const supabase = createClient();
      await supabase.auth.signOut();
      localStorage.removeItem("offline_user_id");
      localStorage.removeItem("offline_user_email");
      localStorage.removeItem("offline_user_role");
      router.push("/login");
      router.refresh();
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

  const displayEmail = email || "user@market.in";
  const displayName = displayEmail.split("@")[0];

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
      }}
    >
      <Layout.Header
        className="sticky top-0 z-50 backdrop-blur-md bg-gradient-to-r from-[rgba(11,15,25,0.95)] via-[rgba(17,24,39,0.95)] to-[rgba(11,15,25,0.95)] px-4 md:px-12"
        style={{
          borderBottom: "1px solid rgba(55, 65, 81, 0.5)",
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
          height: "72px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          color: "#fff",
        }}
      >
        {/* Left Section: Logo & Branding */}
        <Link href="/" className="flex items-center gap-3 hover:opacity-90 transition">
          <div className="w-10 h-10 bg-gradient-to-br from-[#10B981] to-[#059669] rounded-lg flex items-center justify-center shrink-0">
            <span className="text-white font-bold text-lg">MA</span>
          </div>
          <div className="hidden min-[480px]:flex flex-col">
            <span className="text-white font-bold text-sm sm:text-lg leading-tight whitespace-nowrap">
              Market Advisor
            </span>
            <span className="hidden sm:block text-[#9CA3AF] text-xs font-medium whitespace-nowrap">
              NSE Stock Intelligence
            </span>
          </div>
        </Link>

        {/* Center Section: Navigation Links */}
        <div className="hidden md:flex items-center gap-8 text-sm font-semibold tracking-wide">
          <Link
            href="/"
            className={`transition-colors ${
              pathname === "/" ? "text-[#10B981] font-bold" : "text-[#9CA3AF] hover:text-white"
            }`}
          >
            Top 10 Buys
          </Link>
          <Link
            href="/signals"
            className={`transition-colors ${
              pathname === "/signals" ? "text-[#10B981] font-bold" : "text-[#9CA3AF] hover:text-white"
            }`}
          >
            Buy / Sell Signals
          </Link>
          <Link
            href="/strategies"
            className={`transition-colors ${
              pathname === "/strategies" ? "text-[#10B981] font-bold" : "text-[#9CA3AF] hover:text-white"
            }`}
          >
            Strategies
          </Link>
        </div>

        {/* Right Section: User Profile & Actions */}
        <div className="flex items-center gap-3 md:gap-6">
          {/* Notification Bell */}
          <Button
            type="text"
            icon={<BellOutlined className="text-[#D1D5DB] text-lg" />}
            size="large"
            className="hover:bg-white/10 rounded-lg flex items-center justify-center"
          />

          {/* User Profile Dropdown */}
          <Dropdown menu={{ items: userMenuItems }}>
            <div className="flex items-center gap-3 px-2 md:px-3 py-2 rounded-lg hover:bg-white/10 cursor-pointer transition select-none">
              <Avatar
                size={40}
                icon={<UserOutlined />}
                style={{ backgroundColor: "#8B5CF6" }}
                className="shrink-0"
              />
              <div className="hidden md:flex flex-col">
                <span className="text-white font-semibold text-sm leading-tight capitalize max-w-[120px] truncate">
                  {displayName}
                </span>
                <span className="text-[#9CA3AF] text-xs font-normal font-sans max-w-[120px] truncate">
                  {displayEmail}
                </span>
              </div>
            </div>
          </Dropdown>
        </div>
      </Layout.Header>
    </ConfigProvider>
  );
}
