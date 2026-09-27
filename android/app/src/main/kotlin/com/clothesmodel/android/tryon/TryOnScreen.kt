package com.clothesmodel.android.tryon

import android.graphics.BitmapFactory
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun TryOnRoute(
    onAuthenticationExpired: () -> Unit,
    viewModel: TryOnViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
    }
    TryOnScreen(
        state = state,
        onPersonSelected = { viewModel.select(it, "person") },
        onGarmentSelected = { viewModel.select(it, "garment") },
        onCategorySelected = viewModel::setGarmentCategory,
        onGenerate = viewModel::createJob,
    )
}

@Composable
fun TryOnScreen(
    state: TryOnUiState,
    onPersonSelected: (android.net.Uri) -> Unit,
    onGarmentSelected: (android.net.Uri) -> Unit,
    onCategorySelected: (String) -> Unit,
    onGenerate: () -> Unit,
) {
    val personPicker = rememberLauncherForActivityResult(PickVisualMedia()) { uri ->
        uri?.let(onPersonSelected)
    }
    val garmentPicker = rememberLauncherForActivityResult(PickVisualMedia()) { uri ->
        uri?.let(onGarmentSelected)
    }
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        Text(
            "创建试穿",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.semantics { heading() },
        )
        Text("图片会先保存到本机，再由后台可靠上传；离开应用不会中断服务端生成。")
        AssetChoice(
            title = "人物图片",
            selection = state.person,
            onPick = { personPicker.launch(PickVisualMediaRequest(PickVisualMedia.ImageOnly)) },
        )
        AssetChoice(
            title = "服装图片",
            selection = state.garment,
            onPick = { garmentPicker.launch(PickVisualMediaRequest(PickVisualMedia.ImageOnly)) },
        )
        Text("服装类别", modifier = Modifier.semantics { heading() })
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("upper_body" to "上装", "lower_body" to "下装", "dress" to "连衣裙")
                .forEach { (value, label) ->
                    FilterChip(
                        selected = state.garmentCategory == value,
                        onClick = { onCategorySelected(value) },
                        label = { Text(label) },
                    )
                }
        }
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(
            onClick = onGenerate,
            enabled = state.canGenerate,
            modifier = Modifier.fillMaxWidth().sizeIn(minHeight = 48.dp),
        ) {
            if (state.busy) CircularProgressIndicator() else Text("生成一张试穿图")
        }
        if (state.jobId != null) {
            Text("任务 ${state.jobId.take(8)}", style = MaterialTheme.typography.titleMedium)
            Text(jobStateMessage(state.jobState))
        }
        state.resultBytes?.let { bytes ->
            val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
            if (bitmap != null) {
                Image(
                    bitmap = bitmap.asImageBitmap(),
                    contentDescription = "生成的试穿结果",
                    contentScale = ContentScale.Fit,
                    modifier = Modifier.fillMaxWidth().weight(1f),
                )
            }
        }
    }
}

@Composable
private fun AssetChoice(title: String, selection: UploadSelection?, onPick: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(
            when {
                selection?.assetId != null -> "上传完成"
                selection != null -> "上传状态：${selection.state}"
                else -> "尚未选择"
            },
        )
        OutlinedButton(
            onClick = onPick,
            modifier = Modifier.fillMaxWidth().sizeIn(minHeight = 48.dp),
        ) { Text("选择$title") }
    }
}
