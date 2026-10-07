import { Navigate, createBrowserRouter } from 'react-router-dom';

import { AppShell } from './AppShell';
import { ComfyNodePage } from '../features/comfy/ComfyNodePage';
import { ContractStatusPage } from '../features/contract-status/ContractStatusPage';
import { DefaultBackendPage } from '../features/default-backend/DefaultBackendPage';
import { DiagnosticsPage } from '../features/diagnostics/DiagnosticsPage';
import { LoginPage } from '../features/auth/LoginPage';
import { OverviewPage } from '../features/overview/OverviewPage';
import { ProviderAdminPage } from '../features/providers/ProviderAdminPage';
import { RequireAdmin } from '../features/auth/RequireAdmin';
import { SecurityPage } from '../features/security/SecurityPage';
import { StoragePage } from '../features/storage/StoragePage';
import { WorkflowsPage } from '../features/workflows/WorkflowsPage';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAdmin />,
    children: [
      {
        path: '/',
        element: <AppShell />,
        children: [
          { index: true, element: <Navigate replace to="/overview" /> },
          { path: 'overview', element: <OverviewPage /> },
          { path: 'comfy', element: <ComfyNodePage /> },
          { path: 'workflows', element: <WorkflowsPage /> },
          { path: 'providers', element: <ProviderAdminPage /> },
          { path: 'default-backend', element: <DefaultBackendPage /> },
          { path: 'diagnostics', element: <DiagnosticsPage /> },
          { path: 'storage', element: <StoragePage /> },
          { path: 'security', element: <SecurityPage /> },
          { path: 'contract-status', element: <ContractStatusPage /> },
          {
            path: '*',
            element: (
              <main className="page not-found">
                <p className="eyebrow">404</p>
                <h1>这个管理路由不存在。</h1>
              </main>
            ),
          },
        ],
      },
    ],
  },
]);
