package com.clothesmodel.android.history

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.JobModel
import com.clothesmodel.android.data.JobRepository
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class HistoryUiState(
    val jobs: List<JobModel> = emptyList(),
    val nextCursor: String? = null,
    val hasMore: Boolean = false,
    val loading: Boolean = true,
    val loadingMore: Boolean = false,
    val stale: Boolean = false,
    val error: ProblemModel? = null,
    val authenticationExpired: Boolean = false,
)

@HiltViewModel
class HistoryViewModel @Inject constructor(
    private val jobs: JobRepository,
    val imageLoader: AuthenticatedImageLoader,
) : ViewModel() {
    private val mutableState = MutableStateFlow(HistoryUiState())
    val state: StateFlow<HistoryUiState> = mutableState.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true, error = null)
            when (val outcome = jobs.list(limit = 50)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    jobs = outcome.value.items,
                    nextCursor = outcome.value.nextCursor,
                    hasMore = outcome.value.hasMore,
                    loading = false,
                    stale = false,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    stale = mutableState.value.jobs.isNotEmpty(),
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    fun loadMore() {
        val current = mutableState.value
        val cursor = current.nextCursor ?: return
        if (current.loadingMore || !current.hasMore) return
        viewModelScope.launch {
            mutableState.value = current.copy(loadingMore = true)
            when (val outcome = jobs.list(cursor = cursor)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    jobs = mutableState.value.jobs + outcome.value.items,
                    nextCursor = outcome.value.nextCursor,
                    hasMore = outcome.value.hasMore,
                    loadingMore = false,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    loadingMore = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    loadingMore = false,
                    authenticationExpired = true,
                )
            }
        }
    }
}
