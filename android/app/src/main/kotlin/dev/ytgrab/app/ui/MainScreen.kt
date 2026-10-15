package dev.ytgrab.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.ytgrab.app.DownloadStatus
import dev.ytgrab.app.Downloads
import dev.ytgrab.app.MainViewModel
import dev.ytgrab.app.Mode
import dev.ytgrab.app.PartCheck
import dev.ytgrab.app.Parts
import dev.ytgrab.app.R
import dev.ytgrab.app.SavedFile
import dev.ytgrab.app.VideoInfo

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    viewModel: MainViewModel,
    onPaste: () -> Unit,
    onDownload: () -> Unit,
    onCancel: () -> Unit,
    onOpen: (SavedFile) -> Unit,
    onShare: (SavedFile) -> Unit,
) {
    val status by Downloads.status.collectAsStateWithLifecycle()
    val running = status is DownloadStatus.Running

    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.app_name)) }) }) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            LinkRow(viewModel, onPaste)

            viewModel.message?.let {
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            }
            viewModel.info?.let { InfoCard(it, viewModel) }

            ModePicker(viewModel)
            Options(viewModel)

            if (running) {
                OutlinedButton(onClick = onCancel, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                    Text(stringResource(R.string.cancel))
                }
            } else {
                Button(
                    onClick = onDownload,
                    enabled = viewModel.url.isNotBlank() && viewModel.request() != null,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
                ) {
                    Text(stringResource(R.string.download))
                }
            }

            StatusPanel(status, onOpen, onShare)
        }
    }
}

@Composable
private fun LinkRow(viewModel: MainViewModel, onPaste: () -> Unit) {
    OutlinedTextField(
        value = viewModel.url,
        onValueChange = { viewModel.url = it },
        label = { Text(stringResource(R.string.link)) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Go),
        keyboardActions = KeyboardActions(onGo = { viewModel.fetch() }),
        trailingIcon = {
            if (viewModel.url.isNotEmpty()) {
                IconButton(onClick = { viewModel.url = "" }) {
                    Icon(Icons.Filled.Clear, contentDescription = stringResource(R.string.clear))
                }
            }
        },
        modifier = Modifier.fillMaxWidth(),
    )
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        OutlinedButton(onClick = onPaste, modifier = Modifier.weight(1f).heightIn(min = 48.dp)) {
            Text(stringResource(R.string.paste))
        }
        Button(
            onClick = { viewModel.fetch() },
            enabled = !viewModel.fetching && viewModel.url.isNotBlank(),
            modifier = Modifier.weight(1f).heightIn(min = 48.dp),
        ) {
            if (viewModel.fetching) {
                CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                Text(stringResource(R.string.fetching), modifier = Modifier.padding(start = 8.dp))
            } else {
                Text(stringResource(R.string.fetch))
            }
        }
    }
}

@Composable
private fun InfoCard(info: VideoInfo, viewModel: MainViewModel) {
    Card(modifier = Modifier.fillMaxWidth()) {
        viewModel.thumbnail?.let {
            Image(
                bitmap = it,
                contentDescription = stringResource(R.string.thumbnail),
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxWidth().aspectRatio(16f / 9f),
            )
        }
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(info.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            val meta = listOfNotNull(
                info.uploader.takeIf { it.isNotEmpty() },
                formatDuration(info.duration).takeIf { it.isNotEmpty() },
                if (info.isLive) stringResource(R.string.live) else null,
            ).joinToString("  ·  ")
            if (meta.isNotEmpty()) {
                Text(meta, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun ModePicker(viewModel: MainViewModel) {
    Text(
        stringResource(R.string.mode_title),
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.semantics { heading() },
    )
    val modes = listOf(
        Triple(Mode.VIDEO, R.string.mode_video, R.string.mode_video_tip),
        Triple(Mode.AUDIO, R.string.mode_audio, R.string.mode_audio_tip),
        Triple(Mode.MP3, R.string.mode_mp3, R.string.mode_mp3_tip),
        Triple(Mode.TRANSCRIPT, R.string.mode_transcript, R.string.mode_transcript_tip),
    )
    Column(Modifier.selectableGroup()) {
        modes.forEach { (mode, label, tip) ->
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 56.dp)
                    .selectable(
                        selected = viewModel.mode == mode,
                        onClick = { viewModel.mode = mode },
                        role = Role.RadioButton,
                    ),
            ) {
                RadioButton(selected = viewModel.mode == mode, onClick = null)
                Column(modifier = Modifier.padding(start = 12.dp)) {
                    Text(stringResource(label), style = MaterialTheme.typography.bodyLarge)
                    Text(
                        stringResource(tip),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun Options(viewModel: MainViewModel) {
    when (viewModel.mode) {
        Mode.VIDEO -> {
            val heights = viewModel.info?.heights.orEmpty()
            Choice(
                label = stringResource(R.string.resolution),
                options = listOf("best" to stringResource(R.string.best_available)) +
                    heights.map { it.toString() to "${it}p" },
                selected = viewModel.height,
                onSelect = { viewModel.height = it },
            )
            Choice(
                label = stringResource(R.string.container),
                options = listOf(
                    "mp4" to stringResource(R.string.container_mp4),
                    "mkv" to stringResource(R.string.container_mkv),
                ),
                selected = viewModel.container,
                onSelect = { viewModel.container = it },
            )
            Hint(stringResource(R.string.container_tip))
        }
        Mode.AUDIO -> {
            Choice(
                label = stringResource(R.string.stream),
                options = listOf(
                    "best" to stringResource(R.string.audio_best),
                    "opus" to stringResource(R.string.audio_opus),
                    "m4a" to stringResource(R.string.audio_m4a),
                ),
                selected = viewModel.audioStream,
                onSelect = { viewModel.audioStream = it },
            )
            EmbedSwitch(viewModel)
        }
        Mode.MP3 -> {
            Choice(
                label = stringResource(R.string.bitrate),
                options = listOf("0" to stringResource(R.string.bitrate_v0)) +
                    listOf("320", "256", "192", "128").map { it to stringResource(R.string.bitrate_cbr, it) },
                selected = viewModel.bitrate,
                onSelect = { viewModel.bitrate = it },
            )
            EmbedSwitch(viewModel)
        }
        Mode.TRANSCRIPT -> {
            val info = viewModel.info
            when {
                info == null -> Hint(stringResource(R.string.transcript_fetch_first))
                info.transcripts.isEmpty() -> Hint(stringResource(R.string.transcript_none))
                else -> Choice(
                    label = stringResource(R.string.transcript_lang),
                    options = info.transcripts.map {
                        it.code to if (it.auto) stringResource(R.string.transcript_auto, it.code) else it.code
                    },
                    selected = viewModel.transcriptLang.orEmpty(),
                    onSelect = { viewModel.transcriptLang = it },
                )
            }
            Choice(
                label = stringResource(R.string.transcript_format),
                options = listOf(
                    "txt" to stringResource(R.string.transcript_txt),
                    "srt" to stringResource(R.string.transcript_srt),
                    "vtt" to stringResource(R.string.transcript_vtt),
                ),
                selected = viewModel.transcriptFormat,
                onSelect = { viewModel.transcriptFormat = it },
            )
        }
    }
    if (viewModel.partAvailable) PartSection(viewModel)
}

/** "Only a part": a switch, then From and To, and what they come to. */
@Composable
private fun PartSection(viewModel: MainViewModel) {
    val info = viewModel.info ?: return
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .toggleable(value = viewModel.partOn, onValueChange = { viewModel.partOn = it }, role = Role.Switch),
    ) {
        Text(stringResource(R.string.part_switch), modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
        Switch(checked = viewModel.partOn, onCheckedChange = null)
    }
    if (!viewModel.partOn) return

    val check = viewModel.partCheck()
    val badText = (check as? PartCheck.BadTime)?.text
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        TimeField(
            value = viewModel.partFrom,
            onValueChange = { viewModel.partFrom = it },
            label = stringResource(R.string.part_from),
            placeholder = Parts.format(0),
            isError = badText != null && badText == viewModel.partFrom.trim(),
            imeAction = ImeAction.Next,
            modifier = Modifier.weight(1f),
        )
        TimeField(
            value = viewModel.partTo,
            onValueChange = { viewModel.partTo = it },
            label = stringResource(R.string.part_to),
            placeholder = if (info.duration > 0) Parts.format(info.duration) else "",
            isError = badText != null && badText == viewModel.partTo.trim(),
            imeAction = ImeAction.Done,
            modifier = Modifier.weight(1f),
        )
    }

    // An empty pair is where everyone starts, so it reads as a hint, not an error.
    val (summary, isError) = when (check) {
        is PartCheck.Valid -> {
            val (start, end) = check.part
            val text = if (end == null) {
                stringResource(R.string.part_summary_open, Parts.format(start))
            } else {
                stringResource(R.string.part_summary, Parts.format(start), Parts.format(end), Parts.format(end - start))
            }
            text to false
        }
        PartCheck.Empty -> stringResource(R.string.part_empty) to false
        is PartCheck.BadTime -> stringResource(R.string.part_bad_time, check.text) to true
        is PartCheck.StartsLate -> stringResource(R.string.part_start_late, Parts.format(check.duration)) to true
        PartCheck.Backwards -> stringResource(R.string.part_order) to true
        null -> "" to false
    }
    Text(
        summary,
        style = MaterialTheme.typography.bodyMedium,
        color = if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
        // TalkBack reads out what the typed times come to as they change.
        modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
    )
    Hint(stringResource(R.string.part_tip))
    if (viewModel.mode == Mode.VIDEO && viewModel.container == "mkv") {
        Hint(stringResource(R.string.part_mkv_note))
    }
}

/** A From or To time. The number pad has no colon, so a dot or comma does as well. */
@Composable
private fun TimeField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    placeholder: String,
    isError: Boolean,
    imeAction: ImeAction,
    modifier: Modifier,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        placeholder = { Text(placeholder) },
        singleLine = true,
        isError = isError,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal, imeAction = imeAction),
        modifier = modifier,
    )
}

/** A labelled dropdown; TalkBack reads it as one control with its current value. */
@Composable
private fun Choice(label: String, options: List<Pair<String, String>>, selected: String, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    val current = options.firstOrNull { it.first == selected }?.second ?: options.firstOrNull()?.second.orEmpty()
    Box {
        OutlinedCard(
            onClick = { expanded = true },
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 56.dp)
                .semantics {
                    role = Role.DropdownList
                    contentDescription = label
                    stateDescription = current
                },
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(current, style = MaterialTheme.typography.bodyLarge)
                }
                Icon(Icons.Filled.ArrowDropDown, contentDescription = null)
            }
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { (value, text) ->
                DropdownMenuItem(
                    text = { Text(text) },
                    onClick = {
                        onSelect(value)
                        expanded = false
                    },
                )
            }
        }
    }
}

@Composable
private fun EmbedSwitch(viewModel: MainViewModel) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .toggleable(value = viewModel.embed, onValueChange = { viewModel.embed = it }, role = Role.Switch),
    ) {
        Text(stringResource(R.string.embed), modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
        Switch(checked = viewModel.embed, onCheckedChange = null)
    }
}

@Composable
private fun Hint(text: String) {
    Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun StatusPanel(status: DownloadStatus, onOpen: (SavedFile) -> Unit, onShare: (SavedFile) -> Unit) {
    when (status) {
        is DownloadStatus.Running -> Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            if (status.percent >= 0) {
                LinearProgressIndicator(progress = { status.percent / 100f }, modifier = Modifier.fillMaxWidth())
            } else {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            Text(status.state, style = MaterialTheme.typography.bodyMedium)
            if (status.stats.isNotEmpty()) {
                Text(status.stats, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        is DownloadStatus.Done -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(stringResource(R.string.saved_to, status.file.location), style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { onOpen(status.file) }, modifier = Modifier.weight(1f).heightIn(min = 48.dp)) {
                    Text(stringResource(R.string.open))
                }
                OutlinedButton(onClick = { onShare(status.file) }, modifier = Modifier.weight(1f).heightIn(min = 48.dp)) {
                    Text(stringResource(R.string.share))
                }
            }
        }
        is DownloadStatus.Failed -> Column {
            Text(stringResource(R.string.download_failed), style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.error)
            Text(status.message, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.error)
        }
        is DownloadStatus.Cancelled -> Text(stringResource(R.string.cancelled), style = MaterialTheme.typography.bodyMedium)
        DownloadStatus.Idle -> Unit
    }
}

/** 3725 -> "1:02:05", 65 -> "1:05", like the desktop app. */
private fun formatDuration(seconds: Int): String {
    if (seconds <= 0) return ""
    val h = seconds / 3600
    val m = seconds % 3600 / 60
    val s = seconds % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
}
