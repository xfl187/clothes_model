package com.clothesmodel.android.outfits

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clothesmodel.android.data.AssetKindFilter
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.AssetRepository
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.OutfitRepository
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.android.data.ProviderModel
import com.clothesmodel.android.data.ProviderRepository
import com.clothesmodel.contract.model.LayerRole
import com.clothesmodel.contract.model.OutfitRoute
import com.clothesmodel.contract.model.OutfitSession
import com.clothesmodel.contract.model.RemoveOutfitLayerRequest
import com.clothesmodel.contract.model.TryOnJob
import dagger.hilt.android.lifecycle.HiltViewModel
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class WorkbenchUiState(
    val loading: Boolean = true,
    val session: OutfitSession? = null,
    val garments: List<AssetModel> = emptyList(),
    val providers: List<ProviderModel> = emptyList(),
    val selectedRole: LayerRole? = null,
    val selectedGarmentId: UUID? = null,
    val selectedProviderId: UUID? = null,
    val candidates: Int = 1,
    val pendingJob: TryOnJob? = null,
    val busy: Boolean = false,
    val error: ProblemModel? = null,
    val authenticationExpired: Boolean = false,
)

@HiltViewModel
class OutfitWorkbenchViewModel @Inject constructor(
    private val outfits: OutfitRepository,
    private val assets: AssetRepository,
    private val providers: ProviderRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {
    private val sessionId: String = savedStateHandle.get<String>("sessionId").orEmpty()

    private val mutableState = MutableStateFlow(WorkbenchUiState())
    val state: StateFlow<WorkbenchUiState> = mutableState.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true, error = null)
            when (val outcome = outfits.get(UUID.fromString(sessionId))) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    session = outcome.value,
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
        }
        viewModelScope.launch {
            when (val outcome = assets.list(kind = AssetKindFilter.GARMENT)) {
                is Outcome.Success -> mutableState.value =
                    mutableState.value.copy(garments = outcome.value.items)

                else -> Unit
            }
        }
        viewModelScope.launch {
            when (val outcome = providers.available()) {
                is Outcome.Success -> mutableState.value =
                    mutableState.value.copy(providers = outcome.value.items)

                else -> Unit
            }
        }
    }

    fun selectRole(role: LayerRole) {
        mutableState.value = mutableState.value.copy(selectedRole = role, error = null)
    }

    fun selectGarment(assetId: UUID) {
        mutableState.value = mutableState.value.copy(selectedGarmentId = assetId, error = null)
    }

    fun selectProvider(providerId: UUID) {
        mutableState.value = mutableState.value.copy(selectedProviderId = providerId, error = null)
    }

    fun setCandidates(count: Int) {
        mutableState.value = mutableState.value.copy(candidates = count.coerceIn(1, 4))
    }

    fun addLayer() {
        val state = mutableState.value
        val session = state.session ?: return
        val branchId = session.mainBranchId ?: return
        val role = state.selectedRole ?: return
        val garmentId = state.selectedGarmentId ?: return
        viewModelScope.launch {
            mutableState.value = state.copy(busy = true, error = null)
            val key = UUID.randomUUID().toString()
            when (
                val outcome = outfits.addLayer(
                    sessionId = session.id,
                    branchId = branchId,
                    role = role,
                    garmentAssetId = garmentId,
                    providerId = state.selectedProviderId,
                    candidateCount = state.candidates,
                    idempotencyKey = key,
                )
            ) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    session = outcome.value.session,
                    pendingJob = outcome.value.job,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    fun selectOutput(outputId: UUID) {
        val state = mutableState.value
        val session = state.session ?: return
        val branchId = session.mainBranchId ?: return
        val revisionId = session.headRevision?.id ?: return
        val item = state.pendingJob?.items?.firstOrNull { jobItem ->
            jobItem.outputs.any { it.id == outputId }
        } ?: return
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(busy = true, error = null)
            val key = UUID.randomUUID().toString()
            when (
                val outcome = outfits.selectRevision(
                    sessionId = session.id,
                    branchId = branchId,
                    revisionId = revisionId,
                    jobItemId = item.id,
                    outputId = outputId,
                    idempotencyKey = key,
                )
            ) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    session = outcome.value,
                    pendingJob = null,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    fun removeLayer(layerId: UUID) {
        val state = mutableState.value
        val session = state.session ?: return
        val branchId = session.mainBranchId ?: return
        viewModelScope.launch {
            mutableState.value = state.copy(busy = true, error = null)
            when (
                val outcome = outfits.removeLayer(
                    sessionId = session.id,
                    branchId = branchId,
                    layerId = layerId,
                    mode = RemoveOutfitLayerRequest.Mode.remove,
                )
            ) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    session = outcome.value,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    fun switchRoute(route: OutfitRoute) {
        val session = mutableState.value.session ?: return
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(busy = true, error = null)
            val key = UUID.randomUUID().toString()
            when (val outcome = outfits.switchRoute(session.id, route, key)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    session = outcome.value,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    authenticationExpired = true,
                )
            }
        }
    }
}
