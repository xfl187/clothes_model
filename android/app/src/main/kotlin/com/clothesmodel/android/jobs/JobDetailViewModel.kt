package com.clothesmodel.android.jobs

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clothesmodel.android.data.AssetRepository
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.GarmentCategory
import com.clothesmodel.android.data.JobModel
import com.clothesmodel.android.data.JobRepository
import com.clothesmodel.android.data.JobStateDomain
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.android.data.ProviderModel
import com.clothesmodel.android.data.ProviderRepository
import com.clothesmodel.android.data.RefreshPolicy
import dagger.hilt.android.lifecycle.HiltViewModel
import java.time.OffsetDateTime
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

data class RetrySelection(val itemId: UUID)

data class JobDetailUiState(
    val job: JobModel? = null,
    val providers: List<ProviderModel> = emptyList(),
    val garmentCategory: GarmentCategory? = null,
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val stale: Boolean = false,
    val error: ProblemModel? = null,
    val commandError: ProblemModel? = null,
    val authenticationExpired: Boolean = false,
    val busy: Set<String> = emptySet(),
    val retrySelection: RetrySelection? = null,
    val lastSyncedAt: OffsetDateTime? = null,
    val now: OffsetDateTime = OffsetDateTime.now(),
)

@HiltViewModel
class JobDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val jobs: JobRepository,
    private val providers: ProviderRepository,
    private val assets: AssetRepository,
    val imageLoader: AuthenticatedImageLoader,
) : ViewModel() {
    private val jobId: String = savedStateHandle.get<String>("jobId").orEmpty()
    private val mutableState = MutableStateFlow(JobDetailUiState())
    val state: StateFlow<JobDetailUiState> = mutableState.asStateFlow()
    private val commandKeys = mutableMapOf<String, String>()
    private var polling: Job? = null
    private var clock: Job? = null

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true, error = null)
            val id = jobUuid()
            if (id == null) {
                mutableState.value = mutableState.value.copy(
                    loading = false,
                    error = ProblemModel("invalid_id", "任务不存在。", 404, false),
                )
                return@launch
            }
            when (val outcome = jobs.get(id)) {
                is Outcome.Success -> {
                    mutableState.value = mutableState.value.copy(
                        job = outcome.value,
                        loading = false,
                        stale = false,
                        error = null,
                        lastSyncedAt = OffsetDateTime.now(),
                    )
                    loadGarmentCategory(outcome.value.garmentAssetId)
                    loadProviders()
                    if (RefreshPolicy.shouldPoll(outcome.value.state)) {
                        startPolling()
                        startClock()
                    }
                }

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    fun onResumed() {
        if (mutableState.value.job == null) load() else refresh()
        startPolling()
        startClock()
    }

    fun onPaused() {
        stopPolling()
        stopClock()
    }

    fun refresh() {
        val id = jobUuid() ?: return
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(refreshing = true)
            when (val outcome = jobs.get(id)) {
                is Outcome.Success -> {
                    mutableState.value = mutableState.value.copy(
                        job = outcome.value,
                        refreshing = false,
                        stale = false,
                        error = null,
                        lastSyncedAt = OffsetDateTime.now(),
                    )
                    if (isProgressActive(outcome.value.state)) startClock() else stopClock()
                }

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    refreshing = false,
                    stale = mutableState.value.job != null,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    refreshing = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    fun cancelJob() {
        val id = jobUuid() ?: return
        command("cancel-job") { key -> jobs.cancelJob(id, key) }
    }

    fun cancelCandidate(itemId: UUID) {
        command("cancel:$itemId") { key -> jobs.cancelItem(itemId, key) }
    }

    fun requeryCandidate(itemId: UUID) {
        command("requery:$itemId") { key -> jobs.requeryItem(itemId, key) }
    }

    fun finishFailed(itemId: UUID, reason: String) {
        command("finish:$itemId") { key -> jobs.finishFailed(itemId, key, reason) }
    }

    fun requestRetry(itemId: UUID) {
        val current = mutableState.value
        val lockedId = current.job?.lockedProviderId
        val lockedUsable = lockedId != null &&
            current.providers.any { it.id == lockedId && it.selectable }
        if (lockedUsable) {
            retryCandidate(itemId, providerId = null)
        } else {
            mutableState.value = current.copy(retrySelection = RetrySelection(itemId))
        }
    }

    fun confirmRetry(providerId: UUID) {
        val selection = mutableState.value.retrySelection ?: return
        mutableState.value = mutableState.value.copy(retrySelection = null)
        retryCandidate(selection.itemId, providerId)
    }

    fun dismissRetry() {
        mutableState.value = mutableState.value.copy(retrySelection = null)
    }

    private fun retryCandidate(itemId: UUID, providerId: UUID?) {
        command("retry:$itemId") { key -> jobs.retryItem(itemId, key, providerId) }
    }

    fun dismissCommandError() {
        mutableState.value = mutableState.value.copy(commandError = null)
    }

    private fun command(keyToken: String, block: suspend (String) -> Outcome<JobModel>) {
        if (mutableState.value.busy.contains(keyToken)) return
        mutableState.value = mutableState.value.copy(
            busy = mutableState.value.busy + keyToken,
            commandError = null,
        )
        viewModelScope.launch {
            val key = commandKeys.getOrPut(keyToken) { UUID.randomUUID().toString() }
            when (val outcome = block(key)) {
                is Outcome.Success -> {
                    commandKeys.remove(keyToken)
                    mutableState.value = mutableState.value.copy(
                        job = outcome.value,
                        busy = mutableState.value.busy - keyToken,
                        commandError = null,
                        lastSyncedAt = OffsetDateTime.now(),
                    )
                    if (RefreshPolicy.shouldPoll(outcome.value.state)) {
                        startPolling()
                        startClock()
                    }
                }

                is Outcome.Problem -> {
                    if (outcome.problem.code != "network_unavailable") commandKeys.remove(keyToken)
                    mutableState.value = mutableState.value.copy(
                        busy = mutableState.value.busy - keyToken,
                        commandError = outcome.problem,
                    )
                }

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    busy = mutableState.value.busy - keyToken,
                    authenticationExpired = true,
                )
            }
        }
    }

    private fun startPolling() {
        if (polling?.isActive == true) return
        polling = viewModelScope.launch {
            while (isActive) {
                val currentState = mutableState.value.job?.state ?: JobStateDomain.UNKNOWN
                if (!RefreshPolicy.shouldPoll(currentState)) break
                delay(POLL_INTERVAL_MS)
                val id = jobUuid() ?: break
                when (val outcome = jobs.get(id)) {
                    is Outcome.Success -> mutableState.value = mutableState.value.copy(
                        job = outcome.value,
                        stale = false,
                        error = null,
                        lastSyncedAt = OffsetDateTime.now(),
                    )

                    is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                        stale = mutableState.value.job != null,
                        error = outcome.problem,
                    )

                    Outcome.AuthenticationExpired -> {
                        mutableState.value = mutableState.value.copy(authenticationExpired = true)
                        break
                    }
                }
            }
        }
    }

    private fun stopPolling() {
        polling?.cancel()
        polling = null
    }

    private fun startClock() {
        if (clock?.isActive == true) return
        clock = viewModelScope.launch {
            while (isActive) {
                val currentState = mutableState.value.job?.state ?: JobStateDomain.UNKNOWN
                if (!isProgressActive(currentState)) break
                mutableState.value = mutableState.value.copy(now = OffsetDateTime.now())
                delay(CLOCK_INTERVAL_MS)
            }
        }
    }

    private fun stopClock() {
        clock?.cancel()
        clock = null
    }

    private fun loadGarmentCategory(assetId: UUID?) {
        if (assetId == null) return
        viewModelScope.launch {
            when (val outcome = assets.get(assetId)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    garmentCategory = outcome.value.garmentCategory,
                )

                else -> Unit
            }
        }
    }

    private fun loadProviders() {
        viewModelScope.launch {
            when (val outcome = providers.available(limit = 50)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    providers = outcome.value.items,
                )

                else -> Unit
            }
        }
    }

    private fun jobUuid(): UUID? = runCatching { UUID.fromString(jobId) }.getOrNull()

    override fun onCleared() {
        stopPolling()
        stopClock()
        super.onCleared()
    }

    companion object {
        private const val POLL_INTERVAL_MS = 2_000L
        private const val CLOCK_INTERVAL_MS = 1_000L
    }
}
