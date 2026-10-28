import { useMemo, useState } from "react";
import { Avatar, Dropdown, Layout, Menu, theme, Typography } from "antd";
import {
  ApartmentOutlined,
  AuditOutlined,
  BarChartOutlined,
  BellOutlined,
  BookOutlined,
  ClusterOutlined,
  DashboardOutlined,
  LogoutOutlined,
  AimOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";
import { UserManualDrawer } from "@/features/help/UserManualDrawer";

const { Header, Sider, Content } = Layout;

const SIDE_MENUS = [
  { key: "/app/dashboard", icon: <DashboardOutlined />, label: "仪表盘" },
  { key: "/app/leads", icon: <ClusterOutlined />, label: "线索" },
  { key: "/app/accounts", icon: <TeamOutlined />, label: "客户" },
  { key: "/app/opportunities", icon: <AimOutlined />, label: "商机" },
  { key: "/app/targets", icon: <BarChartOutlined />, label: "目标" },
  { key: "/app/reports", icon: <BarChartOutlined />, label: "报表" },
  { key: "/app/todos", icon: <AuditOutlined />, label: "待办审批" },
  { key: "/app/settings", icon: <ApartmentOutlined />, label: "系统管理" },
];

export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const {
    token: { colorBgContainer },
  } = theme.useToken();

  const selectedKey = useMemo(() => {
    const hit = SIDE_MENUS.find((item) => location.pathname.startsWith(item.key));
    return hit?.key ?? "/app/dashboard";
  }, [location.pathname]);

  const displayName = user?.displayName || user?.username || "用户";

  return (
    <Layout className="app-shell">
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        width={220}
        style={{ background: "#0f1c2e" }}
      >
        <div className="app-brand">{collapsed ? "CRM" : "B2B CRM"}</div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={SIDE_MENUS}
          onClick={({ key }) => navigate(key)}
          style={{ background: "#0f1c2e" }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#16324f",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingInline: 20,
          }}
        >
          <Typography.Text className="app-topbar-hint">
            线索 → 客户 → 商机
          </Typography.Text>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <BellOutlined style={{ color: "#fff", fontSize: 16 }} aria-label="通知" />
            <Dropdown
              trigger={["click"]}
              menu={{
                items: [
                  {
                    key: "manual",
                    icon: <BookOutlined />,
                    label: "系统使用说明书",
                  },
                  { type: "divider" },
                  {
                    key: "logout",
                    icon: <LogoutOutlined />,
                    label: "退出登录",
                    danger: true,
                  },
                ],
                onClick: ({ key }) => {
                  if (key === "manual") {
                    setManualOpen(true);
                    return;
                  }
                  if (key === "logout") {
                    void (async () => {
                      setManualOpen(false);
                      await logout();
                      navigate("/login", { replace: true });
                    })();
                  }
                },
              }}
            >
              <button
                type="button"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  border: 0,
                  background: "transparent",
                  color: "#fff",
                  cursor: "pointer",
                  padding: 0,
                }}
                aria-label="打开个人菜单"
              >
                <Avatar size="small" icon={<UserOutlined />} style={{ background: "#1f6feb" }} />
                <span>{displayName}</span>
              </button>
            </Dropdown>
          </div>
        </Header>
        <Content>
          <div className="app-content" style={{ background: colorBgContainer }}>
            <Outlet />
          </div>
        </Content>
      </Layout>
      <UserManualDrawer open={manualOpen} onClose={() => setManualOpen(false)} />
    </Layout>
  );
}
