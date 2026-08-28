package com.atlas.ui.screens.knowledge

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

private data class HubItem(val title: String, val description: String)

private val HUB_ITEMS = listOf(
    HubItem("Documents", "Import and browse PDF, Markdown, TXT, JSON, and CSV files"),
    HubItem("Knowledge", "Browse people, projects, companies, courses, topics, tasks, deadlines, and skills extracted from your documents"),
    HubItem("Timeline", "Deadlines and tasks found in your documents, in chronological order"),
    HubItem("Search", "Search across everything ATLAS has imported"),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun KnowledgeHubScreen(
    onNavigateBack: () -> Unit,
    onNavigateToDocuments: () -> Unit,
    onNavigateToKnowledge: () -> Unit,
    onNavigateToTimeline: () -> Unit,
    onNavigateToSearch: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Knowledge System") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(imageVector = Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            HUB_ITEMS.forEach { item ->
                val onClick = when (item.title) {
                    "Documents" -> onNavigateToDocuments
                    "Knowledge" -> onNavigateToKnowledge
                    "Timeline" -> onNavigateToTimeline
                    else -> onNavigateToSearch
                }
                Surface(
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable(onClick = onClick)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = item.title,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = item.description,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }
    }
}
