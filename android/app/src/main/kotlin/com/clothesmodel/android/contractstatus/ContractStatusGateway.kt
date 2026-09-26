package com.clothesmodel.android.contractstatus

data class ContractProbe(
    val label: String,
    val value: String,
    val successful: Boolean,
)

data class ContractStatusSnapshot(
    val probes: List<ContractProbe>,
)

interface ContractStatusGateway {
    suspend fun loadStatus(): ContractStatusSnapshot
}
