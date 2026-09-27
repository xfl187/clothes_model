import { Navigate, createBrowserRouter } from 'react-router-dom';

import { ContractStatusPage } from '../features/contract-status/ContractStatusPage';
import { AppShell } from './AppShell';
import { LoginPage } from '../features/auth/LoginPage';
import { RequireAdmin } from '../features/auth/RequireAdmin';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAdmin />,
    children: [
      { path: '/', element: <AppShell />, children: [
        { index: true, element: <Navigate replace to="/admin" /> },
        { path: 'admin', element: <main className="page"><p className="eyebrow">Phase 2</p><h1>安全会话已建立</h1></main> },
        { path: 'contract-status', element: <ContractStatusPage /> },
        { path: '*', element: <main className="page not-found"><p className="eyebrow">404</p><h1>这个工程路由不存在。</h1></main> },
      ]},
    ],
  },
]);
