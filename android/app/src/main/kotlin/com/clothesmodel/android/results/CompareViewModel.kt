package com.clothesmodel.android.results

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.JobRepository
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import dagger.hilt.android.lifecycle.HiltViewModel
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class CompareUiState(
    val personAssetId: UUID? = null,
    val resultAssetId: UUID? = null,
    val loading: Boolean = true,
    val error: ProblemModel? = null,
    val authenticationExpired: Boolean = false,
)

@HiltViewModel
class CompareViewModel @Inject constructor(
    private val jobs: JobRepository,
    val imageLoader: AuthenticatedImageLoader,
) : ViewModel() {
    private val mutableState = MutableStateFlow(CompareUiState())
    val state: StateFlow<CompareUiState> = mutableState.asStateFlow()

    fun load(jobId: String, resultAssetId: String) {
        val result = runCatching { UUID.fromString(resultAssetId) }.getOrNull()
        if (result == null) {
            mutableState.value = mutableState.value.copy(
                loading = false,
                error = ProblemModel("invalid_id", "结果不存在。", 404, false),
            )
            return
        }
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true, error = null, resultAssetId = result)
            val id = runCatching { UUID.fromString(jobId) }.getOrNull()
            if (id == null) {
                mutableState.value = mutableState.value.copy(
                    loading = false,
                    error = ProblemModel("invalid_id", "任务不存在。", 404, false),
                )
                return@launch
            }
            when (val outcome = jobs.get(id)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    personAssetId = outcome.value.personAssetIds.firstOrNull(),
                    loading = false,
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
}
