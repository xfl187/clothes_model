package com.clothesmodel.android.app

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.clothesmodel.android.contractstatus.ContractStatusRoute

private const val CONTRACT_STATUS_ROUTE = "contract-status"

@Composable
fun ClothesModelApp() {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = CONTRACT_STATUS_ROUTE,
    ) {
        composable(CONTRACT_STATUS_ROUTE) {
            ContractStatusRoute()
        }
    }
}
