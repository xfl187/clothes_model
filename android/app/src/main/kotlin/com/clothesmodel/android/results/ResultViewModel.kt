package com.clothesmodel.android.results

import android.content.Context
import android.content.Intent
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clothesmodel.android.data.AssetRepository
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.ContentRepository
import com.clothesmodel.android.data.JobModel
import com.clothesmodel.android.data.JobRepository
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ResultUiState(
    val job: JobModel? = null,
    val selectedAssetId: UUID? = null,
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val stale: Boolean = false,
    val busy: Boolean = false,
    val error: ProblemModel? = null,
    val conflict: ProblemModel? = null,
    val message: String? = null,
    val shareIntent: Intent? = null,
    val authenticationExpired: Boolean = false,
)

@HiltViewModel
class ResultViewModel @Inject constructor(
    @param:ApplicationContext private val context: Context,
    savedStateHandle: SavedStateHandle,
    private val jobs: JobRepository,
    private val assets: AssetRepository,
    private val content: ContentRepository,
    val imageLoader: AuthenticatedImageLoader,
) : ViewModel() {
    private val jobId: String = savedStateHandle.get<String>("jobId").orEmpty()
    private val mutableState = MutableStateFlow(ResultUiState())
    val state: StateFlow<ResultUiState> = mutableState.asStateFlow()
    private val retryKeys = mutableMapOf<UUID, String>()

    init {
        load()
    }

    fun load() {
        val id = runCatching { UUID.fromString(jobId) }.getOrNull()
        if (id == null) {
            mutableState.value = mutableState.value.copy(
                loading = false,
                error = ProblemModel("invalid_id", "任务不存在。", 404, false),
            )
            return
        }
        loadJob(id)
    }

    private fun loadJob(id: UUID) {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true, error = null)
            when (val outcome = jobs.get(id)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    job = outcome.value,
                    selectedAssetId = mutableState.value.selectedAssetId
                        ?: firstAvailableOutputAssetId(outcome.value),
                    loading = false,
                    stale = false,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value =
                    mutableState.value.copy(loading = false, authenticationExpired = true)
            }
        }
    }

    fun refresh() {
        val id = runCatching { UUID.fromString(jobId) }.getOrNull() ?: return
        loadJob(id)
    }

    fun select(assetId: UUID) {
        mutableState.value = mutableState.value.copy(selectedAssetId = assetId)
    }

    fun toggleFavorite(assetId: UUID) {
        val job = mutableState.value.job ?: return
        val current = galleryItems(job).firstOrNull { it.output.assetId == assetId }?.output
            ?: return
        viewModelScope.launch {
            when (val outcome = assets.setFavorite(assetId, !current.favorite)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    job = mutableState.value.job?.let {
                        updateOutput(it, assetId) { output -> output.copy(favorite = outcome.value.favorite) }
                    },
                )

                is Outcome.Problem -> mutableState.value =
                    mutableState.value.copy(message = outcome.problem.detail)

                Outcome.AuthenticationExpired -> mutableState.value =
                    mutableState.value.copy(authenticationExpired = true)
            }
        }
    }

    fun deleteContent(assetId: UUID) {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(busy = true, conflict = null)
            when (val outcome = assets.deleteContent(assetId)) {
                is Outcome.Success -> {
                    imageLoader.evict(assetId)
                    mutableState.value = mutableState.value.copy(
                        job = mutableState.value.job?.let {
                            updateOutput(it, assetId) { output ->
                                output.copy(contentAvailable = false)
                            }
                        },
                        selectedAssetId = mutableState.value.job
                            ?.let { updateOutput(it, assetId) { o -> o.copy(contentAvailable = false) } }
                            ?.let { firstAvailableOutputAssetId(it) },
                        busy = false,
                    )
                }

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    conflict = if (outcome.problem.code == "asset_referenced") outcome.problem else null,
                    message = if (outcome.problem.code == "asset_referenced") null else outcome.problem.detail,
                )

                Outcome.AuthenticationExpired -> mutableState.value =
                    mutableState.value.copy(busy = false, authenticationExpired = true)
            }
        }
    }

    fun download(assetId: UUID) {
        viewModelScope.launch {
            when (val outcome = content.download(assetId)) {
                is Outcome.Success -> {
                    val result = downloadToMediaStore(context, assetId, outcome.value)
                    mutableState.value = mutableState.value.copy(
                        message = when (result) {
                            is DownloadResult.Success -> "已保存到图库。"
                            is DownloadResult.Failure -> result.message
                        },
                    )
                }

                is Outcome.Problem -> mutableState.value =
                    mutableState.value.copy(message = outcome.problem.detail)

                Outcome.AuthenticationExpired -> mutableState.value =
                    mutableState.value.copy(authenticationExpired = true)
            }
        }
    }

    fun share(assetId: UUID) {
        viewModelScope.launch {
            when (val outcome = content.download(assetId)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    shareIntent = shareResultIntent(context, assetId, outcome.value),
                )

                is Outcome.Problem -> mutableState.value =
                    mutableState.value.copy(message = outcome.problem.detail)

                Outcome.AuthenticationExpired -> mutableState.value =
                    mutableState.value.copy(authenticationExpired = true)
            }
        }
    }

    fun consumeShareIntent() {
        mutableState.value = mutableState.value.copy(shareIntent = null)
    }

    fun retryCandidate(itemId: UUID) {
        viewModelScope.launch {
            val key = retryKeys.getOrPut(itemId) { UUID.randomUUID().toString() }
            when (val outcome = jobs.retryItem(itemId, key, providerId = null)) {
                is Outcome.Success -> {
                    retryKeys.remove(itemId)
                    mutableState.value = mutableState.value.copy(job = outcome.value)
                }

                is Outcome.Problem -> {
                    if (outcome.problem.code != "network_unavailable") retryKeys.remove(itemId)
                    mutableState.value = mutableState.value.copy(message = outcome.problem.detail)
                }

                Outcome.AuthenticationExpired -> mutableState.value =
                    mutableState.value.copy(authenticationExpired = true)
            }
        }
    }

    fun dismissConflict() {
        mutableState.value = mutableState.value.copy(conflict = null)
    }

    fun dismissMessage() {
        mutableState.value = mutableState.value.copy(message = null)
    }
}
