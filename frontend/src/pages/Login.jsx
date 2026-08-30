import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { Button, Form, Input, message } from 'antd';
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { login, setAuth } from '../services/api';

export default function Login() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const handleSubmit = async (values) => {
    setLoading(true);
    try {
      const data = await login(values.username.trim(), values.password);
      setAuth(data);
      message.success('欢迎回来');
      navigate(location.state?.from || '/', { replace: true });
    } catch (err) {
      message.error(err.response?.data?.detail || '登录失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <main className="login-card" aria-label="登录 AI 用例管理平台">
        <div className="login-brand">
          <div className="login-brand-title">AI用例管理平台</div>
          <div className="login-brand-sub">登录账号，继续你的测试工作</div>
        </div>

        <Form layout="vertical" colon={false} onFinish={handleSubmit} requiredMark={false} className="login-form">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input
              size="large"
              prefix={<UserOutlined />}
              placeholder="请输入用户名"
              autoComplete="username"
              autoFocus
            />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password
              size="large"
              prefix={<LockOutlined />}
              placeholder="请输入密码"
              autoComplete="current-password"
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" size="large" block loading={loading} className="login-submit">
            登录
          </Button>
        </Form>

        <div className="login-switch">
          还没有账号？
          <Link to="/register" state={location.state}>立即注册</Link>
        </div>
      </main>
    </div>
  );
}
