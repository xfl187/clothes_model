export interface HealthProof {
  status: string;
  checkedAt: string;
}

export interface JobProof {
  id: string;
  state: string;
  candidateCount: number;
}

export interface CapabilityProof {
  providerName: string;
  availability: string;
  schemaVersion: number;
  manualMask: boolean;
  multipleCandidates: boolean;
}

export interface ContractStatusSnapshot {
  health: HealthProof;
  job: JobProof;
  capability: CapabilityProof;
}

export interface ContractGateway {
  loadStatus(): Promise<ContractStatusSnapshot>;
}
