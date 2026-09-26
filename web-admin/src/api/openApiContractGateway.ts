import { appConfig } from '../app/config';
import { HealthApi } from './generated/apis/HealthApi';
import { JobsApi } from './generated/apis/JobsApi';
import { ProvidersApi } from './generated/apis/ProvidersApi';
import { Configuration, ResponseError } from './generated/runtime';
import type { ContractGateway, ContractStatusSnapshot } from './contractGateway';

const contractJobId = '01992b5a-0000-7000-8000-000000000002';

export class ContractGatewayError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = 'ContractGatewayError';
  }
}

export class OpenApiContractGateway implements ContractGateway {
  private readonly healthApi: HealthApi;
  private readonly jobsApi: JobsApi;
  private readonly providersApi: ProvidersApi;

  constructor(baseUrl = appConfig.apiBaseUrl) {
    const configuration = new Configuration({
      basePath: baseUrl,
      credentials: 'include',
    });
    this.healthApi = new HealthApi(configuration);
    this.jobsApi = new JobsApi(configuration);
    this.providersApi = new ProvidersApi(configuration);
  }

  async loadStatus(): Promise<ContractStatusSnapshot> {
    try {
      const [health, job, providers] = await Promise.all([
        this.healthApi.getLiveness(),
        this.jobsApi.getJob(
          { jobId: contractJobId },
          { headers: { Prefer: 'example=partiallySucceeded' } },
        ),
        this.providersApi.listAvailableProviders(
          {},
          { headers: { Prefer: 'example=availableProviders' } },
        ),
      ]);
      const provider = providers.items[0];
      if (!provider) {
        throw new ContractGatewayError('契约响应未包含 Provider capability sample。');
      }

      return {
        health: {
          status: health.status,
          checkedAt: health.checkedAt.toISOString(),
        },
        job: {
          id: job.id,
          state: job.state,
          candidateCount: job.items.length,
        },
        capability: {
          providerName: provider.displayName,
          availability: provider.availability,
          schemaVersion: provider.capabilities.schemaVersion,
          manualMask: provider.capabilities.manualMask.supported,
          multipleCandidates: provider.capabilities.multipleCandidates.supported,
        },
      };
    } catch (error) {
      if (error instanceof ContractGatewayError) {
        throw error;
      }
      if (error instanceof ResponseError) {
        throw new ContractGatewayError('契约服务返回了非成功响应。', error.response.status);
      }
      throw new ContractGatewayError('无法连接契约服务。');
    }
  }
}

export const contractGateway = new OpenApiContractGateway();
