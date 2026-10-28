# CRM Frontend

B2B CRM Web 前端（Vite + React + Ant Design）。

本交付聚焦 CYGN-5：**在个人菜单「退出登录」正上方提供「系统使用说明书」入口**，并以抽屉展示后端 `GET /api/v1/help/manual` 返回的 Markdown。

## 本地启动

```bash
npm install
npm run dev
```

默认通过 Vite 代理访问 `http://127.0.0.1:8000` 后端。请先按 `crm-backend/README.md` 启动 API。

默认管理员（后端 seed）：`admin` / `admin123`

## 验收路径（REQ-HELP）

1. 登录后点击右上角头像/姓名
2. 下拉菜单中「系统使用说明书」位于「退出登录」正上方（中间仅允许分隔线）
3. 点击后右侧抽屉加载并渲染说明书；可滚动、可关闭
4. 关闭后仍停留在原业务路由
5. 「退出登录」行为不变；登录页无该入口

## 构建

```bash
npm run build
```
