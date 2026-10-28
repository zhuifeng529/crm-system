import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import { AuthProvider } from "./features/auth/AuthContext";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#1f6feb",
          borderRadius: 6,
          fontFamily:
            '"IBM Plex Sans", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
        },
      }}
    >
      <AuthProvider>
        <App />
      </AuthProvider>
    </ConfigProvider>
  </React.StrictMode>,
);
