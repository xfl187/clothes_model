package com.clothesmodel.android.results

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.assets.AssetImage
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.InlineProblem
import com.clothesmodel.android.ui.components.LoadingState
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.AtelierSpacing

@Composable
fun CompareRoute(
    jobId: String,
    candidateId: String,
    onBack: () -> Unit,
    onAuthenticationExpired: () -> Unit = {},
    viewModel: CompareViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(jobId, candidateId) { viewModel.load(jobId, candidateId) }
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
    }
    CompareScreen(state = state, imageLoader = viewModel.imageLoader, onBack = onBack)
}

@Composable
fun CompareScreen(
    state: CompareUiState,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    onBack: () -> Unit,
) {
    var fraction by remember { mutableFloatStateOf(0.5f) }
    AtelierScaffold(title = "原图对比", onBack = onBack) {
        when {
            state.loading -> LoadingState(label = "正在准备对比")
            state.error != null -> InlineProblem(message = state.error.detail)
            state.resultAssetId != null -> {
                Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.lg)) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .aspectRatio(3f / 4f)
                            .clipToBounds(),
                    ) {
                        AssetImage(
                            assetId = state.resultAssetId,
                            loader = imageLoader,
                            contentDescription = "结果",
                        )
                        Box(
                            modifier = Modifier
                                .fillMaxHeight()
                                .fillMaxWidth(fraction)
                                .clipToBounds(),
                        ) {
                            state.personAssetId?.let { personId ->
                                AssetImage(
                                    assetId = personId,
                                    loader = imageLoader,
                                    contentDescription = "原图",
                                )
                            }
                        }
                        Text(
                            text = "原图",
                            style = MaterialTheme.typography.labelLarge,
                            modifier = Modifier
                                .align(Alignment.TopStart)
                                .semantics { contentDescription = "原图" },
                        )
                        Text(
                            text = "结果",
                            style = MaterialTheme.typography.labelLarge,
                            modifier = Modifier
                                .align(Alignment.TopEnd)
                                .semantics { contentDescription = "结果" },
                        )
                    }

                    Text("拖动滑块或使用下方按钮比较原图与结果。")
                    Slider(
                        value = fraction,
                        onValueChange = { fraction = it },
                        modifier = Modifier
                            .fillMaxWidth()
                            .sizeIn(minHeight = AtelierSpacing.minTouchTarget)
                            .semantics { contentDescription = "对比位置" },
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.md)) {
                        OutlinedButton(
                            onClick = { fraction = 1f },
                            shape = AtelierShapes.Secondary,
                            modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                        ) { Text("显示原图") }
                        OutlinedButton(
                            onClick = { fraction = 0f },
                            shape = AtelierShapes.Secondary,
                            modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                        ) { Text("显示结果") }
                    }
                }
            }
        }
    }
}
