package com.clothesmodel.android.app

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.clothesmodel.android.connection.ConnectionRoute

private const val CONNECTION_ROUTE = "connection"

@Composable
fun ClothesModelApp() {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = CONNECTION_ROUTE,
    ) {
        composable(CONNECTION_ROUTE) {
            ConnectionRoute()
        }
    }
}
