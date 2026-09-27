import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAdminSession } from './adminSessionState';

export function RequireAdmin() {
  const session = useAdminSession();
  const location = useLocation();
  if (session.state === 'loading') return <main className="page"><p>正在恢复安全会话…</p></main>;
  if (session.state !== 'authenticated') return <Navigate replace to="/login" state={{ from: location.pathname }} />;
  return <Outlet />;
}
