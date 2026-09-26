package com.clothesmodel.android.di

import com.clothesmodel.android.BuildConfig
import com.clothesmodel.android.contractstatus.ContractProbeConfiguration
import com.clothesmodel.android.contractstatus.ContractStatusGateway
import com.clothesmodel.android.contractstatus.GeneratedContractStatusGateway
import com.clothesmodel.contract.api.HealthApi
import com.clothesmodel.contract.api.JobsApi
import com.clothesmodel.contract.api.ProvidersApi
import com.clothesmodel.contract.infrastructure.ApiClient
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class ContractBindings {
    @Binds
    abstract fun bindContractStatusGateway(
        implementation: GeneratedContractStatusGateway,
    ): ContractStatusGateway
}

@Module
@InstallIn(SingletonComponent::class)
object ContractNetworkModule {
    @Provides
    @Singleton
    fun provideApiClient(): ApiClient {
        val baseUrl = BuildConfig.API_BASE_URL.ifBlank { "https://example.invalid/" }
        return if (BuildConfig.CONTRACT_TOKEN.isBlank()) {
            ApiClient(baseUrl = baseUrl)
        } else {
            ApiClient(
                baseUrl = baseUrl,
                authName = "AppBearer",
                bearerToken = BuildConfig.CONTRACT_TOKEN,
            )
        }
    }

    @Provides
    fun provideHealthApi(client: ApiClient): HealthApi = client.createService(HealthApi::class.java)

    @Provides
    fun provideJobsApi(client: ApiClient): JobsApi = client.createService(JobsApi::class.java)

    @Provides
    fun provideProvidersApi(client: ApiClient): ProvidersApi = client.createService(ProvidersApi::class.java)

    @Provides
    fun provideProbeConfiguration(): ContractProbeConfiguration = ContractProbeConfiguration(
        sampleJobId = BuildConfig.SAMPLE_JOB_ID.takeIf(String::isNotBlank),
    )
}
