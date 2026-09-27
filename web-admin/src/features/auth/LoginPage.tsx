import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { AdminAuthError } from '../../api/adminAuthGateway';
import { useAdminSession } from './adminSessionState';
import styles from './LoginPage.module.css';

const messages = { invalid: 'Admin Token 无效。', throttled: '尝试次数过多，请稍后再试。', offline: '无法连接服务器。', expired: '会话已过期。', unknown: '登录暂时失败。' };

export function LoginPage() {
  const session = useAdminSession();
  const [token, setToken] = useState(''); const [error, setError] = useState(''); const [loading, setLoading] = useState(false); const [submitted, setSubmitted] = useState(false);
  const navigate = useNavigate(); const location = useLocation();
  if (session.state === 'authenticated' && !submitted) return <Navigate replace to="/admin" />;
  const from = typeof location.state === 'object' && location.state && 'from' in location.state && typeof location.state.from === 'string' && location.state.from.startsWith('/') && !location.state.from.startsWith('//') ? location.state.from : '/admin';
  return <main className={styles.page}><form className={styles.panel} onSubmit={async event => {
    event.preventDefault(); const credential = token; setSubmitted(true); setLoading(true); setError('');
    try { await session.login(credential); setToken(''); navigate(from, { replace: true }); }
    catch (cause) { setSubmitted(false); setError(cause instanceof AdminAuthError ? messages[cause.kind] : messages.unknown); }
    finally { setToken(''); setLoading(false); }
  }}><p className="eyebrow">Quiet Control Room</p><h1>管理员登录</h1><p>Token 只用于本次登录交换，不会写入浏览器存储。</p><label>Admin Token<input autoComplete="off" type="password" value={token} onChange={event => setToken(event.target.value)} /></label>{error && <p role="alert" className={styles.error}>{error}</p>}<button disabled={loading || token.length < 32}>{loading ? '验证中…' : '安全登录'}</button></form></main>;
}
