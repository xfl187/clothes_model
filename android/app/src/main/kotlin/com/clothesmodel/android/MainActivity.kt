package com.clothesmodel.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.clothesmodel.android.app.ClothesModelApp
import com.clothesmodel.android.ui.theme.ClothesModelTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            ClothesModelTheme {
                ClothesModelApp()
            }
        }
    }
}
