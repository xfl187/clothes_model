import { appConfig } from '../app/config';
import { AdminConfigurationApi } from './generated/apis/AdminConfigurationApi';
import { AuthenticationApi } from './generated/apis/AuthenticationApi';
import { DiagnosticsApi } from './generated/apis/DiagnosticsApi';
import { ProvidersApi } from './generated/apis/ProvidersApi';
import { StorageApi } from './generated/apis/StorageApi';
import { WorkflowsApi } from './generated/apis/WorkflowsApi';
import type { AppCredentialRotation } from './generated/models/AppCredentialRotation';
import type { AppCredentialStatus } from './generated/models/AppCredentialStatus';
import type { CleanupResult } from './generated/models/CleanupResult';
import type { ComfyNodeConfiguration } from './generated/models/ComfyNodeConfiguration';
import type { ComfyNodeConfigurationRequest } from './generated/models/ComfyNodeConfigurationRequest';
import type { ConnectionTestResult } from './generated/models/ConnectionTestResult';
import type { DefaultProviderConfiguration } from './generated/models/DefaultProviderConfiguration';
import type { DiagnosticJobDetail } from './generated/models/DiagnosticJobDetail';
import type { DiagnosticJobPage } from './generated/models/DiagnosticJobPage';
import type { JobCommandResult } from './generated/models/JobCommandResult';
import type { ProviderConfig } from './generated/models/ProviderConfig';
import type { RetentionPolicy } from './generated/models/RetentionPolicy';
import type { StorageScanResult } from './generated/models/StorageScanResult';
import type { StorageStatus } from './generated/models/StorageStatus';
import type { SystemOverview } from './generated/models/SystemOverview';
import type { WorkflowValidationResult } from './generated/models/WorkflowValidationResult';
import type { WorkflowVersion } from './generated/models/WorkflowVersion';
import { Configuration, FetchError, ResponseError } from './generated/runtime';

export type { WorkflowVersion };

let csrfToken = '';

export function setCsrfToken(token: string): void {
  csrfToken = token;
}

export interface ProblemInfo {
  status: number;
  code: string;
  detail: string;
  retryable: boolean;
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ResponseError && error.response.status === 401;
}

export function isOffline(error: unknown): boolean {
  return error instanceof FetchError;
}

export function problemSummary(error: unknown): string {
  if (error instanceof FetchError) return '无法连接后端服务，请检查网络。';
  if (error instanceof ResponseError) return `请求失败（HTTP ${error.response.status}）。`;
  return '操作失败，请稍后重试。';
}

export async function problemFrom(error: unknown): Promise<ProblemInfo> {
  if (error instanceof FetchError) {
    return { status: 0, code: 'offline', detail: '无法连接后端服务，请检查网络或稍后重试。', retryable: true };
  }
  if (error instanceof ResponseError) {
    try {
      const body = (await error.response.clone().json()) as {
        code?: unknown;
        detail?: unknown;
        retryable?: unknown;
      };
      return {
        status: error.response.status,
        code: typeof body.code === 'string' ? body.code : 'unknown',
        detail: typeof body.detail === 'string' && body.detail.trim()
          ? body.detail
          : '请求失败，请稍后重试。',
        retryable: body.retryable === true,
      };
    } catch {
      return { status: error.response.status, code: 'unknown', detail: '请求失败，请稍后重试。', retryable: false };
    }
  }
  return { status: 0, code: 'unknown', detail: '操作失败，请稍后重试。', retryable: false };
}

export interface DiagnosticListParams {
  cursor?: string;
  state?: string;
  limit?: number;
}

export interface AdminApi {
  overview(): Promise<SystemOverview>;
  comfyNode(): Promise<ComfyNodeConfiguration>;
  updateComfyNode(request: ComfyNodeConfigurationRequest): Promise<ComfyNodeConfiguration>;
  testComfyNode(): Promise<ConnectionTestResult>;
  listProviders(): Promise<ProviderConfig[]>;
  listWorkflows(): Promise<WorkflowVersion[]>;
  validateWorkflow(id: string): Promise<WorkflowValidationResult>;
  activateWorkflow(id: string, expectedActive?: string): Promise<WorkflowVersion>;
  retireWorkflow(id: string): Promise<WorkflowVersion>;
  defaultProvider(): Promise<DefaultProviderConfiguration>;
  setDefaultProvider(providerId: string): Promise<DefaultProviderConfiguration>;
  listDiagnosticJobs(params: DiagnosticListParams): Promise<DiagnosticJobPage>;
  diagnosticJob(id: string): Promise<DiagnosticJobDetail>;
  cancelJob(id: string): Promise<JobCommandResult>;
  cancelJobItem(id: string): Promise<JobCommandResult>;
  retryJobItem(id: string): Promise<JobCommandResult>;
  requeryJobItem(id: string): Promise<JobCommandResult>;
  finishJobItemFailed(id: string, reason: string): Promise<JobCommandResult>;
  storageStatus(): Promise<StorageStatus>;
  retention(): Promise<RetentionPolicy>;
  updateRetention(unfavoritedOutputDays: number, intermediateFileDays: number): Promise<RetentionPolicy>;
  scanStorage(): Promise<StorageScanResult>;
  cleanup(scanId: string): Promise<CleanupResult>;
  appCredential(): Promise<AppCredentialStatus>;
  rotateAppCredential(): Promise<AppCredentialRotation>;
}

export function createAdminApi(): AdminApi {
  const configuration = new Configuration({
    basePath: appConfig.apiBaseUrl,
    credentials: 'include',
    apiKey: (name) => (name === 'X-CSRF-Token' ? csrfToken : ''),
  });
  const admin = new AdminConfigurationApi(configuration);
  const auth = new AuthenticationApi(configuration);
  const diagnostics = new DiagnosticsApi(configuration);
  const providers = new ProvidersApi(configuration);
  const storage = new StorageApi(configuration);
  const workflows = new WorkflowsApi(configuration);
  const key = () => crypto.randomUUID();

  return {
    overview: () => admin.getSystemOverview(),
    comfyNode: () => admin.getComfyNodeConfiguration(),
    updateComfyNode: (request) => admin.updateComfyNodeConfiguration({ comfyNodeConfigurationRequest: request }),
    testComfyNode: () => admin.testComfyNodeConnection({ idempotencyKey: key() }),
    listProviders: async () => (await providers.listProviderConfigs()).items,
    listWorkflows: async () => (await workflows.listWorkflowVersions()).items,
    validateWorkflow: (id) => workflows.validateWorkflowVersion({ workflowVersionId: id, idempotencyKey: key() }),
    activateWorkflow: (id, expectedActive) =>
      workflows.activateWorkflowVersion({
        workflowVersionId: id,
        workflowActivateRequest: {
          confirmNewJobsOnly: true,
          expectedCurrentActiveWorkflowVersionId: expectedActive ?? null,
        },
        idempotencyKey: key(),
      }),
    retireWorkflow: (id) =>
      workflows.retireWorkflowVersion({
        workflowVersionId: id,
        workflowRetireRequest: { confirmNewJobsOnly: true },
        idempotencyKey: key(),
      }),
    defaultProvider: () => admin.getDefaultProviderConfiguration(),
    setDefaultProvider: (providerId) =>
      admin.updateDefaultProviderConfiguration({
        defaultProviderUpdateRequest: { providerId, confirmNewJobsOnly: true },
      }),
    listDiagnosticJobs: async (params) =>
      diagnostics.listDiagnosticJobs({ cursor: params.cursor, state: params.state as never, limit: params.limit }),
    diagnosticJob: (id) => diagnostics.getDiagnosticJob({ jobId: id }),
    cancelJob: (id) => diagnostics.adminCancelJob({ jobId: id, idempotencyKey: key() }),
    cancelJobItem: (id) => diagnostics.adminCancelJobItem({ jobItemId: id, idempotencyKey: key() }),
    retryJobItem: (id) => diagnostics.adminRetryJobItem({ jobItemId: id, idempotencyKey: key() }),
    requeryJobItem: (id) => diagnostics.adminRequeryJobItem({ jobItemId: id, idempotencyKey: key() }),
    finishJobItemFailed: (id, reason) =>
      diagnostics.adminFinishJobItemAsFailed({
        jobItemId: id,
        finishFailedRequest: { reason },
        idempotencyKey: key(),
      }),
    storageStatus: () => storage.getStorageStatus(),
    retention: () => admin.getRetentionPolicy(),
    updateRetention: (unfavoritedOutputDays, intermediateFileDays) =>
      admin.updateRetentionPolicy({
        retentionPolicyUpdateRequest: { unfavoritedOutputDays, intermediateFileDays },
      }),
    scanStorage: () => storage.scanStorage({ idempotencyKey: key() }),
    cleanup: (scanId) =>
      storage.cleanupStorage({
        cleanupRequest: { scanId, confirmIrreversible: true },
        idempotencyKey: key(),
      }),
    appCredential: () => auth.getAppCredentialStatus(),
    rotateAppCredential: () => auth.rotateAppCredential({ idempotencyKey: key() }),
  };
}
