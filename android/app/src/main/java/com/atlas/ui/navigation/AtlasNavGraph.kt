package com.atlas.ui.navigation

import androidx.compose.runtime.Composable
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.atlas.ui.screens.about.AboutScreen
import com.atlas.ui.screens.chat.ChatScreen
import com.atlas.ui.screens.chat.ChatViewModel
import com.atlas.ui.screens.memory.MemoryScreen
import com.atlas.ui.screens.memory.MemoryViewModel
import com.atlas.ui.screens.documents.DocumentsScreen
import com.atlas.ui.screens.documents.DocumentsViewModel
import com.atlas.ui.screens.knowledge.KnowledgeHubScreen
import com.atlas.ui.screens.knowledge.KnowledgeScreen
import com.atlas.ui.screens.knowledge.KnowledgeViewModel
import com.atlas.ui.screens.permissions.PermissionCenterScreen
import com.atlas.ui.screens.permissions.PermissionCenterViewModel
import com.atlas.ui.screens.assistant.PersonalAssistantScreen
import com.atlas.ui.screens.assistant.PersonalAssistantViewModel
import com.atlas.ui.screens.timeline.TimelineScreen
import com.atlas.ui.screens.timeline.TimelineViewModel
import com.atlas.ui.screens.search.SearchScreen
import com.atlas.ui.screens.search.SearchViewModel
import com.atlas.ui.screens.settings.SettingsScreen
import com.atlas.ui.screens.splash.SplashScreen
import com.atlas.ui.screens.voice.VoiceScreen
import com.atlas.ui.screens.voice.VoiceViewModel

object Routes {
    const val SPLASH = "splash"
    const val CHAT = "chat"
    const val SETTINGS = "settings"
    const val ABOUT = "about"
    const val MEMORY = "memory"
    const val KNOWLEDGE_HUB = "knowledge_hub"
    const val DOCUMENTS = "documents"
    const val KNOWLEDGE = "knowledge"
    const val TIMELINE = "timeline"
    const val SEARCH = "search"
    const val VOICE = "voice"
    const val PERMISSIONS = "permissions"
    const val ASSISTANT = "assistant" // Phase 10
}

@Composable
fun AtlasNavGraph(
    navController: NavHostController = rememberNavController()
) {
    NavHost(
        navController = navController,
        startDestination = Routes.SPLASH
    ) {
        composable(Routes.SPLASH) {
            SplashScreen(
                onSplashFinished = {
                    navController.navigate(Routes.CHAT) {
                        popUpTo(Routes.SPLASH) { inclusive = true }
                    }
                }
            )
        }
        composable(Routes.CHAT) {
            val viewModel: ChatViewModel = hiltViewModel()
            ChatScreen(
                viewModel = viewModel,
                onNavigateToSettings = { navController.navigate(Routes.SETTINGS) },
                onNavigateToAbout = { navController.navigate(Routes.ABOUT) },
                onNavigateToMemory = { navController.navigate(Routes.MEMORY) },
                onNavigateToKnowledgeHub = { navController.navigate(Routes.KNOWLEDGE_HUB) },
                onNavigateToVoice = { navController.navigate(Routes.VOICE) },
                onNavigateToAssistant = { navController.navigate(Routes.ASSISTANT) }
            )
        }
        composable(Routes.SETTINGS) {
            SettingsScreen(
                onNavigateBack = { navController.popBackStack() },
                onNavigateToPermissions = { navController.navigate(Routes.PERMISSIONS) }
            )
        }
        composable(Routes.ABOUT) {
            AboutScreen(
                onNavigateBack = { navController.popBackStack() }
            )
        }
        composable(Routes.MEMORY) {
            val viewModel: MemoryViewModel = hiltViewModel()
            MemoryScreen(
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }
        composable(Routes.KNOWLEDGE_HUB) {
            KnowledgeHubScreen(
                onNavigateBack = { navController.popBackStack() },
                onNavigateToDocuments = { navController.navigate(Routes.DOCUMENTS) },
                onNavigateToKnowledge = { navController.navigate(Routes.KNOWLEDGE) },
                onNavigateToTimeline = { navController.navigate(Routes.TIMELINE) },
                onNavigateToSearch = { navController.navigate(Routes.SEARCH) }
            )
        }
        composable(Routes.DOCUMENTS) {
            val viewModel: DocumentsViewModel = hiltViewModel()
            DocumentsScreen(
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }
        composable(Routes.KNOWLEDGE) {
            val viewModel: KnowledgeViewModel = hiltViewModel()
            KnowledgeScreen(
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }
        composable(Routes.TIMELINE) {
            val viewModel: TimelineViewModel = hiltViewModel()
            TimelineScreen(
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }
        composable(Routes.SEARCH) {
            val viewModel: SearchViewModel = hiltViewModel()
            SearchScreen(
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }
        composable(Routes.VOICE) {
            val viewModel: VoiceViewModel = hiltViewModel()
            VoiceScreen(
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }
        composable(Routes.PERMISSIONS) {
            val viewModel: PermissionCenterViewModel = hiltViewModel()
            PermissionCenterScreen(
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }
        composable(Routes.ASSISTANT) {
            val viewModel: PersonalAssistantViewModel = hiltViewModel()
            PersonalAssistantScreen(
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }
    }
}
