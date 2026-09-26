import { Navigate, createBrowserRouter } from 'react-router-dom';

import { ContractStatusPage } from '../features/contract-status/ContractStatusPage';
import { AppShell } from './AppShell';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate replace to="/contract-status" /> },
      { path: 'contract-status', element: <ContractStatusPage /> },
      {
        path: '*',
        element: (
          <main className="page not-found">
            <p className="eyebrow">404</p>
            <h1>这个工程路由不存在。</h1>
          </main>
        ),
      },
    ],
  },
]);
