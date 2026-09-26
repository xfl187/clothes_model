import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import type { ContractGateway } from '../../api/contractGateway';
import { ContractGatewayProvider } from '../../app/ContractGatewayContext';
import { ContractStatusPage } from './ContractStatusPage';

const loadStatus = vi.fn().mockResolvedValue({
  health: { status: 'ok', checkedAt: '2026-09-25T00:00:00.000Z' },
  job: {
    id: '01992b5a-0000-7000-8000-000000000002',
    state: 'partially_succeeded',
    candidateCount: 2,
  },
  capability: {
    providerName: 'ComfyUI · precise-vton',
    availability: 'available',
    schemaVersion: 1,
    manualMask: true,
    multipleCandidates: true,
  },
});
const gateway: ContractGateway = { loadStatus };

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ContractGatewayProvider gateway={gateway}>
        <ContractStatusPage />
      </ContractGatewayProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => loadStatus.mockClear());

test('renders adapter-owned health, job state, and capability proof', async () => {
  renderPage();

  expect(await screen.findByText('partially_succeeded')).toBeInTheDocument();
  expect(screen.getByText('ComfyUI · precise-vton')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '服务健康结论' })).toBeInTheDocument();
  expect(screen.getAllByText('支持')).toHaveLength(2);

  await userEvent.setup().click(screen.getByRole('button', { name: '重新检查' }));
  expect(loadStatus).toHaveBeenCalledTimes(2);
});
