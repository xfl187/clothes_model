package com.clothesmodel.android.app

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.clothesmodel.android.connection.ConnectionRoute
import com.clothesmodel.android.tryon.TryOnRoute

private const val CONNECTION_ROUTE = "connection"
private const val TRY_ON_ROUTE = "try-on"

@Composable
fun ClothesModelApp() {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = CONNECTION_ROUTE,
    ) {
        composable(CONNECTION_ROUTE) {
            ConnectionRoute(
                onConnected = {
                    navController.navigate(TRY_ON_ROUTE) {
                        popUpTo(CONNECTION_ROUTE) { inclusive = true }
                    }
                },
            )
        }
        composable(TRY_ON_ROUTE) {
            TryOnRoute(
                onAuthenticationExpired = {
                    navController.navigate(CONNECTION_ROUTE) {
                        popUpTo(TRY_ON_ROUTE) { inclusive = true }
                    }
                },
            )
        }
    }
}
