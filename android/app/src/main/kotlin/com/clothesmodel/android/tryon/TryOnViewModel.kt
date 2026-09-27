package com.clothesmodel.android.tryon

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.room.Room
import com.clothesmodel.android.connection.ConnectionStore
import com.clothesmodel.android.connection.TokenVault
import com.clothesmodel.android.imports.ImportStaging
import com.clothesmodel.android.imports.PendingImport
import com.clothesmodel.android.imports.PendingImportDatabase
import com.clothesmodel.android.imports.PendingImportScheduler
import com.clothesmodel.contract.api.AssetsApi
import com.clothesmodel.contract.api.JobsApi
import com.clothesmodel.contract.api.ProvidersApi
import com.clothesmodel.contract.infrastructure.ApiClient
import com.clothesmodel.contract.model.AssetKind
import com.clothesmodel.contract.model.CreateJobRequest
import com.clothesmodel.contract.model.GenerationOptions
import com.clothesmodel.contract.model.JobState
import com.clothesmodel.contract.model.ProviderAvailability
import com.clothesmodel.contract.model.TryOnMode
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class UploadSelection(val importId: String, val state: String, val assetId: String? = null)

data class TryOnUiState(
    val person: UploadSelection? = null,
    val garment: UploadSelection? = null,
    val garmentCategory: String = "upper_body",
    val busy: Boolean = false,
    val jobId: String? = null,
    val jobState: String? = null,
    val resultBytes: ByteArray? = null,
    val error: String? = null,
    val authenticationExpired: Boolean = false,
) {
    val canGenerate: Boolean
        get() = person?.assetId != null && garment?.assetId != null && !busy
}

fun jobStateMessage(state: String?): String = when (state) {
    "queued" -> "任务已排队"
    "waiting_provider" -> "等待 Provider 可用"
    "preparing" -> "正在准备私有图片"
    "running" -> "正在生成，离开页面也会继续"
    "needs_attention" -> "结果状态不确定，需要人工处理"
    "succeeded" -> "生成完成"
    "failed" -> "生成失败"
    "cancelled" -> "任务已取消"
    else -> "等待创建任务"
}

@HiltViewModel
class TryOnViewModel @Inject constructor(
    @param:ApplicationContext private val context: Context,
) : ViewModel() {
    private val database = Room.databaseBuilder(
        context,
        PendingImportDatabase::class.java,
        "pending-imports.db",
    ).build()
    private val drafts = TryOnDraftStore(context)
    private val mutableState = MutableStateFlow(TryOnUiState())
    val state: StateFlow<TryOnUiState> = mutableState.asStateFlow()

    init {
        viewModelScope.launch {
            val draft = drafts.snapshot()
            mutableState.value = mutableState.value.copy(
                garmentCategory = draft.garmentCategory,
                jobId = draft.activeJobId,
            )
            while (isActive) {
                val currentDraft = drafts.snapshot()
                refreshImports(currentDraft.personImportId, currentDraft.garmentImportId)
                delay(1_000)
            }
        }
        viewModelScope.launch {
            val active = drafts.snapshot().activeJobId
            if (active != null) pollJob(UUID.fromString(active))
        }
    }

    fun select(uri: Uri, kind: String) {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(busy = true, error = null)
            runCatching {
                withContext(Dispatchers.IO) {
                    val staged = ImportStaging(context).copy(uri)
                    val id = UUID.randomUUID().toString()
                    val contentType = context.contentResolver.getType(uri)
                        ?.takeIf { it == "image/png" || it == "image/jpeg" }
                        ?: "image/jpeg"
                    database.pendingImports().save(
                        PendingImport(
                            id = id,
                            stagedPath = staged.absolutePath,
                            displayName = if (kind == "person") "人物图片" else "服装图片",
                            contentType = contentType,
                            assetKind = if (kind == "person") AssetKind.person.value else AssetKind.garment.value,
                        ),
                    )
                    drafts.selectImport(kind, id)
                    PendingImportScheduler(context).enqueue(id)
                    id
                }
            }.onSuccess { id ->
                val selection = UploadSelection(id, "staged")
                mutableState.value = if (kind == "person") {
                    mutableState.value.copy(person = selection, busy = false)
                } else {
                    mutableState.value.copy(garment = selection, busy = false)
                }
            }.onFailure {
                mutableState.value = mutableState.value.copy(busy = false, error = "无法保存所选图片。")
            }
        }
    }

    fun setGarmentCategory(category: String) {
        mutableState.value = mutableState.value.copy(garmentCategory = category)
        viewModelScope.launch { drafts.garmentMetadata(category) }
    }

    fun createJob() {
        val personId = mutableState.value.person?.assetId ?: return
        val garmentId = mutableState.value.garment?.assetId ?: return
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(busy = true, error = null)
            val access = authenticatedApis() ?: return@launch
            val providers = access.providers.listAvailableProviders().body()?.items.orEmpty()
            val provider = providers.firstOrNull {
                it.isDefault == true && it.availability == ProviderAvailability.available
            } ?: providers.firstOrNull { it.availability == ProviderAvailability.available }
            if (provider == null || provider.capabilities.outputConstraints.maxCandidates < 1) {
                mutableState.value = mutableState.value.copy(
                    busy = false,
                    error = "没有可用于新任务的默认 Provider。",
                )
                return@launch
            }
            val draft = drafts.snapshot()
            val key = draft.createIdempotencyKey ?: UUID.randomUUID().toString().also {
                drafts.rememberCreateKey(it)
            }
            val response = access.jobs.createJob(
                key,
                CreateJobRequest(
                    personAssetIds = listOf(UUID.fromString(personId)),
                    garmentAssetId = UUID.fromString(garmentId),
                    providerId = provider.id,
                    mode = TryOnMode.precise_try_on,
                    generationOptions = GenerationOptions(candidateCount = 1),
                ),
            )
            if (response.code() == 401) return@launch expireAuthentication()
            val job = response.body()
            if (job == null) {
                mutableState.value = mutableState.value.copy(busy = false, error = "任务创建失败，请重试。")
                return@launch
            }
            drafts.activeJob(job.id.toString())
            mutableState.value = mutableState.value.copy(
                busy = false,
                jobId = job.id.toString(),
                jobState = job.state.value,
            )
            pollJob(job.id)
        }
    }

    private suspend fun refreshImports(personImportId: String?, garmentImportId: String?) {
        val imports = database.pendingImports().all().associateBy(PendingImport::id)
        fun selection(id: String?) = id?.let(imports::get)?.let {
            UploadSelection(it.id, it.state, it.assetId)
        }
        mutableState.value = mutableState.value.copy(
            person = selection(personImportId) ?: mutableState.value.person,
            garment = selection(garmentImportId) ?: mutableState.value.garment,
        )
    }

    private suspend fun pollJob(id: UUID) {
        while (true) {
            val access = authenticatedApis() ?: return
            val response = access.jobs.getJob(id)
            if (response.code() == 401) return expireAuthentication()
            val job = response.body()
            if (job == null) {
                mutableState.value = mutableState.value.copy(error = "无法同步任务状态。")
                return
            }
            mutableState.value = mutableState.value.copy(jobState = job.state.value, busy = false)
            if (job.state == JobState.succeeded || job.state == JobState.partially_succeeded) {
                val output = job.items.flatMap { it.outputs }.firstOrNull { it.contentAvailable }
                if (output != null) {
                    val content = access.assets.downloadAssetContent(output.assetId)
                    if (content.code() == 401) return expireAuthentication()
                    mutableState.value = mutableState.value.copy(
                        resultBytes = content.body()?.bytes(),
                        error = if (content.isSuccessful) null else "无法读取私有结果。",
                    )
                }
                return
            }
            if (job.state in setOf(JobState.failed, JobState.cancelled, JobState.needs_attention)) return
            delay(2_000)
        }
    }

    private suspend fun authenticatedApis(): Apis? {
        val vault = TokenVault(context)
        val connection = ConnectionStore(context, vault).snapshot()
        val token = vault.read()
        if (connection.serverUrl == null || token == null) {
            expireAuthentication()
            return null
        }
        val client = ApiClient(connection.serverUrl, authName = "AppBearer", bearerToken = token)
        return Apis(
            client.createService(ProvidersApi::class.java),
            client.createService(JobsApi::class.java),
            client.createService(AssetsApi::class.java),
        )
    }

    private suspend fun expireAuthentication() {
        ConnectionStore(context, TokenVault(context)).authenticationExpired()
        mutableState.value = mutableState.value.copy(
            busy = false,
            authenticationExpired = true,
            error = "认证已失效；重新连接后任务会继续同步。",
        )
    }

    override fun onCleared() {
        database.close()
        super.onCleared()
    }

    private data class Apis(
        val providers: ProvidersApi,
        val jobs: JobsApi,
        val assets: AssetsApi,
    )
}
