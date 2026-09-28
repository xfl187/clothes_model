package com.clothesmodel.android.assets

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.AssetReferenceModel
import com.clothesmodel.android.data.AssetRepository
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import dagger.hilt.android.lifecycle.HiltViewModel
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class AssetDetailUiState(
    val asset: AssetModel? = null,
    val references: List<AssetReferenceModel> = emptyList(),
    val loading: Boolean = true,
    val busy: Boolean = false,
    val error: ProblemModel? = null,
    val conflict: ProblemModel? = null,
    val authenticationExpired: Boolean = false,
)

@HiltViewModel
class AssetDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val assets: AssetRepository,
    val imageLoader: AuthenticatedImageLoader,
) : ViewModel() {
    private val assetId: String = savedStateHandle.get<String>("assetId").orEmpty()
    private val mutableState = MutableStateFlow(AssetDetailUiState())
    val state: StateFlow<AssetDetailUiState> = mutableState.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true, error = null)
            val id = runCatching { UUID.fromString(assetId) }.getOrNull()
            if (id == null) {
                mutableState.value = mutableState.value.copy(
                    loading = false,
                    error = ProblemModel("invalid_id", "素材不存在。", 404, false),
                )
                return@launch
            }
            when (val outcome = assets.get(id)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    asset = outcome.value,
                    loading = false,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    authenticationExpired = true,
                )
            }
            loadReferences(id)
        }
    }

    private suspend fun loadReferences(id: UUID) {
        when (val outcome = assets.references(id)) {
            is Outcome.Success -> mutableState.value = mutableState.value.copy(
                references = outcome.value.items.filter { it.active },
            )

            is Outcome.Problem -> Unit
            Outcome.AuthenticationExpired ->
                mutableState.value = mutableState.value.copy(authenticationExpired = true)
        }
    }

    fun toggleFavorite() {
        val asset = mutableState.value.asset ?: return
        viewModelScope.launch {
            when (val outcome = assets.setFavorite(asset.id, !asset.favorite)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    asset = outcome.value,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    authenticationExpired = true,
                )
            }
        }
    }

    fun deleteContent() {
        val asset = mutableState.value.asset ?: return
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(busy = true, conflict = null, error = null)
            when (val outcome = assets.deleteContent(asset.id)) {
                is Outcome.Success -> {
                    imageLoader.evict(asset.id)
                    mutableState.value = mutableState.value.copy(
                        asset = outcome.value,
                        references = emptyList(),
                        busy = false,
                    )
                }

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    conflict = if (outcome.problem.code == "asset_referenced") {
                        outcome.problem
                    } else {
                        null
                    },
                    error = if (outcome.problem.code == "asset_referenced") {
                        null
                    } else {
                        outcome.problem
                    },
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    fun dismissConflict() {
        mutableState.value = mutableState.value.copy(conflict = null)
    }
}
