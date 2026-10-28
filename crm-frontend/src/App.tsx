import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Spin } from "antd";
import { AppLayout } from "./app/AppLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { useAuth } from "./features/auth/AuthContext";
import { PlaceholderPage } from "./pages/PlaceholderPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <Spin size="large" tip="加载中…" />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/app"
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route
            path="dashboard"
            element={
              <PlaceholderPage
                title="仪表盘"
                description="经营概况占位。请通过右上角个人菜单打开「系统使用说明书」。"
              />
            }
          />
          <Route path="leads" element={<PlaceholderPage title="线索" />} />
          <Route path="accounts" element={<PlaceholderPage title="客户" />} />
          <Route path="opportunities" element={<PlaceholderPage title="商机" />} />
          <Route path="targets" element={<PlaceholderPage title="目标" />} />
          <Route path="reports" element={<PlaceholderPage title="报表" />} />
          <Route path="todos" element={<PlaceholderPage title="待办审批" />} />
          <Route path="settings" element={<PlaceholderPage title="系统管理" />} />
        </Route>
        <Route path="/" element={<Navigate to="/app/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/app/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
