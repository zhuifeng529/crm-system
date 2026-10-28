import { useState } from "react";
import { Alert, Button, Form, Input } from "antd";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth, getErrorMessage } from "./AuthContext";

interface LoginForm {
  username: string;
  password: string;
}

export function LoginPage() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!loading && user) {
    return <Navigate to="/app/dashboard" replace />;
  }

  const onFinish = async (values: LoginForm) => {
    setSubmitting(true);
    setError(null);
    try {
      await login(values.username.trim(), values.password);
      navigate("/app/dashboard", { replace: true });
    } catch (err) {
      setError(getErrorMessage(err, "登录失败，请检查用户名和密码"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>B2B CRM</h1>
        <p>线索 → 客户 → 商机</p>
        {error ? (
          <Alert
            type="error"
            showIcon
            message={error}
            style={{ marginBottom: 16 }}
          />
        ) : null}
        <Form<LoginForm>
          layout="vertical"
          requiredMark={false}
          onFinish={(values) => void onFinish(values)}
          >
          <Form.Item
            label="用户名"
            name="username"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input autoComplete="username" size="large" placeholder="请输入用户名" />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password
              autoComplete="current-password"
              size="large"
              placeholder="请输入密码"
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" block size="large" loading={submitting}>
            登录
          </Button>
        </Form>
      </div>
    </div>
  );
}
