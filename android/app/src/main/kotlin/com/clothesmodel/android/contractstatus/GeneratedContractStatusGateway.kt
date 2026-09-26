package com.clothesmodel.android.contractstatus

import com.clothesmodel.contract.api.HealthApi
import com.clothesmodel.contract.api.JobsApi
import com.clothesmodel.contract.api.ProvidersApi
import java.util.UUID
import javax.inject.Inject

class GeneratedContractStatusGateway @Inject constructor(
    private val healthApi: HealthApi,
    private val jobsApi: JobsApi,
    private val providersApi: ProvidersApi,
    private val probeConfiguration: ContractProbeConfiguration,
) : ContractStatusGateway {
    override suspend fun loadStatus(): ContractStatusSnapshot = ContractStatusSnapshot(
        probes = listOf(
            probe("Health") {
                val response = healthApi.getLiveness()
                requireSuccessful(response.code(), response.isSuccessful)
                response.body()?.status?.value ?: error("Health response had no body")
            },
            probe("Job state") {
                val jobId = probeConfiguration.sampleJobId
                    ?.let(UUID::fromString)
                    ?: error("Debug sample job is not configured")
                val response = jobsApi.getJob(jobId)
                requireSuccessful(response.code(), response.isSuccessful)
                response.body()?.state?.value ?: error("Job response had no body")
            },
            probe("Capabilities") {
                val response = providersApi.listAvailableProviders(limit = 1)
                requireSuccessful(response.code(), response.isSuccessful)
                val provider = response.body()?.items?.firstOrNull()
                    ?: error("Provider response had no items")
                val categories = provider.capabilities.garmentCategories.propertyValues.joinToString()
                "${provider.displayName}: $categories"
            },
        ),
    )

    private suspend fun probe(label: String, request: suspend () -> String): ContractProbe =
        runCatching { request() }
            .fold(
                onSuccess = { value -> ContractProbe(label, value, successful = true) },
                onFailure = { error ->
                    ContractProbe(
                        label = label,
                        value = error.message ?: error::class.simpleName.orEmpty(),
                        successful = false,
                    )
                },
            )

    private fun requireSuccessful(code: Int, successful: Boolean) {
        check(successful) { "HTTP $code" }
    }
}

data class ContractProbeConfiguration(
    val sampleJobId: String?,
)
