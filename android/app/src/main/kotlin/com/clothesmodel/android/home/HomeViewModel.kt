package com.clothesmodel.android.home

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

data class HomeUiState(
    val recentJobs: List<JobModel> = emptyList(),
    val loading: Boolean = true,
    val error: ProblemModel? = null,
    val stale: Boolean = false,
    val authenticationExpired: Boolean = false,
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val jobs: JobRepository,
    val imageLoader: AuthenticatedImageLoader,
) : ViewModel() {
    private val mutableState = MutableStateFlow(HomeUiState())
    val state: StateFlow<HomeUiState> = mutableState.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true, error = null)
            when (val outcome = jobs.list(limit = 3)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    recentJobs = outcome.value.items,
                    loading = false,
                    stale = false,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    stale = mutableState.value.recentJobs.isNotEmpty(),
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    authenticationExpired = true,
                )
            }
        }
    }
}
