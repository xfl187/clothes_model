/* eslint-disable react-refresh/only-export-components -- provider and hook form one boundary */
import { createContext, use } from 'react';
import type { PropsWithChildren } from 'react';

import type { ContractGateway } from '../api/contractGateway';
import { contractGateway } from '../api/openApiContractGateway';

const ContractGatewayContext = createContext<ContractGateway | null>(null);

export function ContractGatewayProvider({
  children,
  gateway = contractGateway,
}: PropsWithChildren<{ gateway?: ContractGateway }>) {
  return <ContractGatewayContext value={gateway}>{children}</ContractGatewayContext>;
}

export function useContractGateway(): ContractGateway {
  const gateway = use(ContractGatewayContext);
  if (!gateway) {
    throw new Error('ContractGatewayProvider is missing.');
  }
  return gateway;
}
