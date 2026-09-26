package com.clothesmodel.android.contractstatus

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface ContractStatusUiState {
    data object Loading : ContractStatusUiState
    data class Content(val snapshot: ContractStatusSnapshot) : ContractStatusUiState
}

@HiltViewModel
class ContractStatusViewModel @Inject constructor(
    private val gateway: ContractStatusGateway,
) : ViewModel() {
    private val mutableState = MutableStateFlow<ContractStatusUiState>(ContractStatusUiState.Loading)
    val state: StateFlow<ContractStatusUiState> = mutableState.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        mutableState.value = ContractStatusUiState.Loading
        viewModelScope.launch {
            mutableState.value = ContractStatusUiState.Content(gateway.loadStatus())
        }
    }
}
