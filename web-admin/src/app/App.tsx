import { RouterProvider } from 'react-router-dom';

import { AppProviders } from './AppProviders';
import { ErrorBoundary } from './ErrorBoundary';
import { router } from './router';

export function App() {
  return (
    <ErrorBoundary>
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    </ErrorBoundary>
  );
}
