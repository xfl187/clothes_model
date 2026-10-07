package com.clothesmodel.android.outfits

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clothesmodel.android.data.AssetKindFilter
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.AssetRepository
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.OutfitRepository
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.contract.model.OutfitSession
import dagger.hilt.android.lifecycle.HiltViewModel
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class OutfitListUiState(
    val loading: Boolean = true,
    val sessions: List<OutfitSession> = emptyList(),
    val persons: List<AssetModel> = emptyList(),
    val error: ProblemModel? = null,
    val authenticationExpired: Boolean = false,
    val pickerOpen: Boolean = false,
    val creating: Boolean = false,
    val createdSession: OutfitSession? = null,
)

@HiltViewModel
class OutfitSessionListViewModel @Inject constructor(
    private val outfits: OutfitRepository,
    private val assets: AssetRepository,
) : ViewModel() {
    private val mutableState = MutableStateFlow(OutfitListUiState())
    val state: StateFlow<OutfitListUiState> = mutableState.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true, error = null)
            when (val outcome = outfits.list()) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    sessions = outcome.value,
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
    }

    fun openPicker() {
        mutableState.value = mutableState.value.copy(pickerOpen = true, error = null)
        viewModelScope.launch {
            when (val outcome = assets.list(kind = AssetKindFilter.PERSON)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    persons = outcome.value.items,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired ->
                    mutableState.value = mutableState.value.copy(authenticationExpired = true)
            }
        }
    }

    fun closePicker() {
        mutableState.value = mutableState.value.copy(pickerOpen = false)
    }

    fun create(personAssetId: UUID) {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(creating = true, error = null)
            val key = UUID.randomUUID().toString()
            when (val outcome = outfits.create(personAssetId, null, key)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    creating = false,
                    pickerOpen = false,
                    createdSession = outcome.value,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    creating = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    creating = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    fun consumeCreated() {
        mutableState.value = mutableState.value.copy(createdSession = null)
        refresh()
    }

    fun toggleFavorite(session: OutfitSession) {
        viewModelScope.launch {
            when (
                val outcome = outfits.setFavorite(session.id, !session.favorite)
            ) {
                is Outcome.Success -> {
                    val updated = outcome.value
                    mutableState.value = mutableState.value.copy(
                        sessions = mutableState.value.sessions.map {
                            if (it.id == updated.id) updated else it
                        },
                    )
                }

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired ->
                    mutableState.value = mutableState.value.copy(authenticationExpired = true)
            }
        }
    }
}
