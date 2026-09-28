package com.clothesmodel.android.navigation

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.clothesmodel.android.assets.AssetCenterRoute
import com.clothesmodel.android.assets.AssetDetailRoute
import com.clothesmodel.android.connection.ConnectionRoute
import com.clothesmodel.android.create.CreateWizardRoute
import com.clothesmodel.android.history.HistoryRoute
import com.clothesmodel.android.home.HomeRoute
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.LocalAtelierTokens

@Composable
fun AppBottomBar(
    currentRoute: String?,
    onSelect: (String) -> Unit,
) {
    NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
        Destinations.tabRoutes.forEach { (route, label) ->
            val selected = currentRoute == route
            NavigationBarItem(
                selected = selected,
                onClick = { onSelect(route) },
                alwaysShowLabel = true,
                icon = {
                    Box(
                        modifier = Modifier
                            .size(22.dp)
                            .background(
                                color = if (selected) {
                                    MaterialTheme.colorScheme.primaryContainer
                                } else {
                                    LocalAtelierTokens.current.line
                                },
                                shape = if (selected) AtelierShapes.PrimaryButton else CircleShape,
                            ),
                    )
                },
                label = { Text(label) },
            )
        }
    }
}

@Composable
fun MainTabs(
    onCreate: () -> Unit,
    onOpenAsset: (String) -> Unit,
    onOpenJob: (String) -> Unit,
    onAuthenticationExpired: () -> Unit = {},
) {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route

    Scaffold(
        bottomBar = {
            AppBottomBar(currentRoute = currentRoute) { route ->
                navController.navigate(route) {
                    popUpTo(navController.graph.findStartDestination().id) {
                        saveState = true
                    }
                    launchSingleTop = true
                    restoreState = true
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = Destinations.HOME,
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            composable(Destinations.HOME) {
                HomeRoute(
                    onCreate = onCreate,
                    onOpenJob = onOpenJob,
                    onAuthenticationExpired = onAuthenticationExpired,
                )
            }
            composable(Destinations.ASSETS) {
                AssetCenterRoute(
                    onCreate = onCreate,
                    onOpenAsset = onOpenAsset,
                    onAuthenticationExpired = onAuthenticationExpired,
                )
            }
            composable(Destinations.HISTORY) {
                HistoryRoute(
                    onOpenJob = onOpenJob,
                    onAuthenticationExpired = onAuthenticationExpired,
                )
            }
        }
    }
}

@Composable
fun ClothesModelNavHost(navController: NavHostController = rememberNavController()) {
    NavHost(
        navController = navController,
        startDestination = Destinations.CONNECTION,
    ) {
        composable(
            route = Destinations.CONNECTION,
            arguments = listOf(
                navArgument(Destinations.ARG_REAUTH) {
                    type = NavType.BoolType
                    defaultValue = false
                },
            ),
        ) {
            ConnectionRoute(
                onConnected = {
                    navController.navigate(Destinations.MAIN) {
                        popUpTo(navController.graph.id) { inclusive = true }
                    }
                },
            )
        }
        composable(Destinations.MAIN) {
            MainTabs(
                onCreate = { navController.navigate(Destinations.CREATE) },
                onOpenAsset = { navController.navigate(Destinations.assetDetail(it)) },
                onOpenJob = { navController.navigate(Destinations.jobDetail(it)) },
                onAuthenticationExpired = {
                    navController.navigate(Destinations.connection(reauth = true)) {
                        popUpTo(navController.graph.id) { inclusive = true }
                    }
                },
            )
        }
        composable(
            route = Destinations.ASSET_DETAIL,
            arguments = listOf(navArgument(Destinations.ARG_ASSET_ID) { type = NavType.StringType }),
        ) { entry ->
            AssetDetailRoute(
                assetId = entry.arguments?.getString(Destinations.ARG_ASSET_ID).orEmpty(),
                onBack = { navController.popBackStack() },
                onAuthenticationExpired = {
                    navController.navigate(Destinations.connection(reauth = true)) {
                        popUpTo(navController.graph.id) { inclusive = true }
                    }
                },
            )
        }
        composable(Destinations.CREATE) {
            CreateWizardRoute(
                onBack = { navController.popBackStack() },
                onCreated = { navController.navigate(Destinations.jobDetail(it)) },
                onOpenAssets = {
                    navController.navigate(Destinations.MAIN) {
                        popUpTo(navController.graph.id) { inclusive = true }
                    }
                },
                onAuthenticationExpired = {
                    navController.navigate(Destinations.connection(reauth = true)) {
                        popUpTo(navController.graph.id) { inclusive = true }
                    }
                },
            )
        }
        composable(
            route = Destinations.JOB_DETAIL,
            arguments = listOf(navArgument(Destinations.ARG_JOB_ID) { type = NavType.StringType }),
        ) { entry ->
            JobDetailRoute(
                jobId = entry.arguments?.getString(Destinations.ARG_JOB_ID).orEmpty(),
                onBack = { navController.popBackStack() },
                onOpenResults = { navController.navigate(Destinations.results(it)) },
            )
        }
        composable(
            route = Destinations.RESULTS,
            arguments = listOf(navArgument(Destinations.ARG_JOB_ID) { type = NavType.StringType }),
        ) { entry ->
            val jobId = entry.arguments?.getString(Destinations.ARG_JOB_ID).orEmpty()
            ResultRoute(
                jobId = jobId,
                onBack = { navController.popBackStack() },
                onCompare = { navController.navigate(Destinations.compare(jobId, it)) },
                onMask = { navController.navigate(Destinations.mask(jobId, it)) },
            )
        }
        composable(
            route = Destinations.COMPARE,
            arguments = listOf(
                navArgument(Destinations.ARG_JOB_ID) { type = NavType.StringType },
                navArgument(Destinations.ARG_CANDIDATE_ID) { type = NavType.StringType },
            ),
        ) { entry ->
            CompareRoute(
                jobId = entry.arguments?.getString(Destinations.ARG_JOB_ID).orEmpty(),
                candidateId = entry.arguments?.getString(Destinations.ARG_CANDIDATE_ID).orEmpty(),
                onBack = { navController.popBackStack() },
            )
        }
        composable(
            route = Destinations.MASK,
            arguments = listOf(
                navArgument(Destinations.ARG_JOB_ID) { type = NavType.StringType },
                navArgument(Destinations.ARG_CANDIDATE_ID) { type = NavType.StringType },
            ),
        ) { entry ->
            MaskEditorRoute(
                jobId = entry.arguments?.getString(Destinations.ARG_JOB_ID).orEmpty(),
                candidateId = entry.arguments?.getString(Destinations.ARG_CANDIDATE_ID).orEmpty(),
                onBack = { navController.popBackStack() },
            )
        }
    }
}
