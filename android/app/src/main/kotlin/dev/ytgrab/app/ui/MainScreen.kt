package dev.ytgrab.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material3.AlertDialog
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
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.pluralStringResource
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.ytgrab.app.DownloadRequest
import dev.ytgrab.app.Downloads
import dev.ytgrab.app.ItemState
import dev.ytgrab.app.MainViewModel
import dev.ytgrab.app.Mode
import dev.ytgrab.app.PartCheck
import dev.ytgrab.app.Parts
import dev.ytgrab.app.QueueItem
import dev.ytgrab.app.R
import dev.ytgrab.app.SavedFile
import dev.ytgrab.app.VideoInfo

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    viewModel: MainViewModel,
    onPaste: () -> Unit,
    onDownload: () -> Unit,
    onRetry: (Long) -> Unit,
    onOpen: (SavedFile) -> Unit,
    onShare: (SavedFile) -> Unit,
) {
    val queue by Downloads.queue.collectAsStateWithLifecycle()
    val busy = queue.any { it.state == ItemState.WAITING || it.state == ItemState.RUNNING }

    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.app_name)) }) }) { padding ->
        // One list for the form and the downloads, so a long playlist scrolls smoothly.
        LazyColumn(
            modifier = Modifier
                .padding(padding)
                .imePadding(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { LinkRow(viewModel, onPaste) }
            viewModel.message?.let {
                item { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
            }
            if (viewModel.links.isNotEmpty()) {
                item { BatchCard(viewModel.links.size) }
            } else {
                viewModel.shown?.let { item { InfoCard(it, viewModel) } }
            }
            item { ModePicker(viewModel) }
            item {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) { Options(viewModel) }
            }
            item { DownloadButton(viewModel, busy, onDownload) }
            if (queue.isNotEmpty()) {
                item { QueueHeader(queue, busy) }
                items(queue, key = { it.id }) { QueueRow(it, onRetry, onOpen, onShare) }
            }
        }
    }
}

@Composable
private fun LinkRow(viewModel: MainViewModel, onPaste: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
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
            // Several links download as they are; Fetch reads one.
            Button(
                onClick = { viewModel.fetch() },
                enabled = !viewModel.fetching && viewModel.url.isNotBlank() && viewModel.links.isEmpty(),
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
}

/** Several links in the box: they download one after another, as they are. */
@Composable
private fun BatchCard(count: Int) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                pluralStringResource(R.plurals.batch_title, count, count),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            Text(
                stringResource(R.string.batch_note),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
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
            val playlist = info.playlist
            val meta = if (info.video || playlist == null) {
                listOfNotNull(
                    info.uploader.takeIf { it.isNotEmpty() },
                    formatDuration(info.duration).takeIf { it.isNotEmpty() },
                    if (info.isLive) stringResource(R.string.live) else null,
                )
            } else {
                listOfNotNull(
                    stringResource(R.string.playlist_label),
                    info.uploader.takeIf { it.isNotEmpty() },
                    pluralStringResource(R.plurals.playlist_videos, playlist.entries.size, playlist.entries.size),
                )
            }.joinToString("  ·  ")
            if (meta.isNotEmpty()) {
                Text(meta, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            // A video that sits in a playlist: that video, or the whole list.
            if (info.video && playlist != null) {
                Column(Modifier.selectableGroup()) {
                    ChoiceRow(stringResource(R.string.playlist_this), !viewModel.wholePlaylist) { viewModel.wholePlaylist = false }
                    ChoiceRow(
                        pluralStringResource(R.plurals.playlist_whole, playlist.entries.size, playlist.entries.size),
                        viewModel.wholePlaylist,
                    ) { viewModel.wholePlaylist = true }
                    if (playlist.title.isNotEmpty()) {
                        Text(
                            stringResource(R.string.playlist_name, playlist.title),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(start = 52.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ChoiceRow(text: String, selected: Boolean, onClick: () -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .selectable(selected = selected, onClick = onClick, role = Role.RadioButton),
    ) {
        RadioButton(selected = selected, onClick = null)
        Text(text, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.padding(start = 12.dp))
    }
}

@Composable
private fun ModePicker(viewModel: MainViewModel) {
    Column {
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
}

@Composable
private fun Options(viewModel: MainViewModel) {
    when (viewModel.mode) {
        Mode.VIDEO -> {
            Choice(
                label = stringResource(R.string.resolution),
                options = listOf("best" to stringResource(R.string.best_available)) +
                    viewModel.heights.map { it.toString() to "${it}p" },
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
            val tracks = viewModel.transcripts
            when {
                tracks == null -> Hint(stringResource(R.string.transcript_fetch_first))
                tracks.isEmpty() -> Hint(stringResource(R.string.transcript_none))
                else -> Choice(
                    label = stringResource(R.string.transcript_lang),
                    options = tracks.map {
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
    val info = viewModel.shown ?: return
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

/** Download now, or join the queue - for one video, a playlist or several links. */
@Composable
private fun DownloadButton(viewModel: MainViewModel, busy: Boolean, onDownload: () -> Unit) {
    val count = viewModel.count
    val text = when {
        viewModel.links.isNotEmpty() ->
            pluralStringResource(if (busy) R.plurals.queue_add_links else R.plurals.download_links, count, count)
        viewModel.takesPlaylist ->
            pluralStringResource(if (busy) R.plurals.queue_add_n else R.plurals.download_n, count, count)
        else -> stringResource(if (busy) R.string.queue_add else R.string.download)
    }
    Button(
        onClick = onDownload,
        enabled = viewModel.url.isNotBlank() && viewModel.requests() != null,
        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
    ) {
        Text(text)
    }
}

@Composable
private fun QueueHeader(queue: List<QueueItem>, busy: Boolean) {
    var asking by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.weight(1f).semantics { heading() }) {
                Text(stringResource(R.string.queue_title), style = MaterialTheme.typography.titleMedium)
                Text(
                    stringResource(R.string.queue_summary, queue.count { it.state == ItemState.DONE }, queue.size),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (busy) {
                TextButton(onClick = { asking = true }) { Text(stringResource(R.string.queue_cancel_all)) }
            }
            if (queue.any { it.finished }) {
                TextButton(onClick = { Downloads.clearFinished() }) { Text(stringResource(R.string.queue_clear)) }
            }
        }
    }
    if (asking) {
        AlertDialog(
            onDismissRequest = { asking = false },
            text = { Text(stringResource(R.string.queue_cancel_all_ask)) },
            confirmButton = {
                TextButton(onClick = {
                    asking = false
                    Downloads.cancelAll()
                }) { Text(stringResource(R.string.queue_cancel_all)) }
            },
            dismissButton = {
                TextButton(onClick = { asking = false }) { Text(stringResource(R.string.queue_keep)) }
            },
        )
    }
}

/** One download: what it is, how far it has got, and what can be done with it. */
@Composable
private fun QueueRow(
    item: QueueItem,
    onRetry: (Long) -> Unit,
    onOpen: (SavedFile) -> Unit,
    onShare: (SavedFile) -> Unit,
) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                item.label,
                style = MaterialTheme.typography.titleSmall,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            val state = when (item.state) {
                ItemState.WAITING -> stringResource(R.string.queue_waiting)
                ItemState.RUNNING -> if (item.cancelling) stringResource(R.string.cancelling)
                                     else item.progress.ifEmpty { stringResource(R.string.starting) }
                ItemState.DONE -> stringResource(R.string.saved)
                ItemState.FAILED -> stringResource(R.string.download_failed)
                ItemState.CANCELLED -> stringResource(R.string.cancelled)
            }
            val stats = if (item.state == ItemState.RUNNING && !item.cancelling) item.stats else ""
            Text(
                listOf(summary(item.request), state, stats).filter { it.isNotEmpty() }.joinToString("  ·  "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (item.state == ItemState.RUNNING) {
                if (item.percent >= 0 && !item.cancelling) {
                    LinearProgressIndicator(progress = { item.percent / 100f }, modifier = Modifier.fillMaxWidth())
                } else {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }
            }
            if (item.state == ItemState.FAILED && !item.error.isNullOrEmpty()) {
                Text(item.error, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.error)
            }
            item.file?.takeIf { item.state == ItemState.DONE }?.let {
                Text(stringResource(R.string.saved_to, it.location), style = MaterialTheme.typography.bodySmall)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                when (item.state) {
                    ItemState.RUNNING -> OutlinedButton(
                        onClick = { Downloads.cancel(item.id) },
                        enabled = !item.cancelling,
                        modifier = Modifier.heightIn(min = 48.dp),
                    ) { Text(stringResource(R.string.cancel)) }
                    ItemState.DONE -> {
                        item.file?.let { file ->
                            Button(onClick = { onOpen(file) }, modifier = Modifier.heightIn(min = 48.dp)) {
                                Text(stringResource(R.string.open))
                            }
                            OutlinedButton(onClick = { onShare(file) }, modifier = Modifier.heightIn(min = 48.dp)) {
                                Text(stringResource(R.string.share))
                            }
                        }
                        RemoveButton(item)
                    }
                    ItemState.FAILED, ItemState.CANCELLED -> {
                        Button(onClick = { onRetry(item.id) }, modifier = Modifier.heightIn(min = 48.dp)) {
                            Text(stringResource(R.string.queue_retry))
                        }
                        RemoveButton(item)
                    }
                    ItemState.WAITING -> RemoveButton(item)
                }
            }
        }
    }
}

@Composable
private fun RemoveButton(item: QueueItem) {
    TextButton(onClick = { Downloads.remove(item.id) }, modifier = Modifier.heightIn(min = 48.dp)) {
        Text(stringResource(R.string.queue_remove))
    }
}

/** The settings a download uses, in a few words: "MP3 · 192 kbps · 16:15–16:45". */
@Composable
private fun summary(request: DownloadRequest): String {
    val bits = when (request.mode) {
        "video" -> listOf(
            stringResource(R.string.mode_video),
            if (request.quality == "best") stringResource(R.string.summary_best)
            else stringResource(R.string.summary_up_to, request.quality),
            request.container.uppercase(),
        )
        "audio" -> listOf(stringResource(R.string.mode_audio)) +
            listOfNotNull(mapOf("opus" to "Opus", "m4a" to "AAC")[request.quality])
        "mp3" -> listOf(
            "MP3",
            if (request.quality == "0") "V0" else stringResource(R.string.summary_kbps, request.quality),
        )
        else -> listOf(stringResource(R.string.mode_transcript), request.quality, request.container.uppercase())
    }
    val part = request.part?.let { (start, end) -> "${Parts.format(start)}–${end?.let(Parts::format).orEmpty()}" }
    return (bits + listOfNotNull(part)).joinToString("  ·  ")
}

/** 3725 -> "1:02:05", 65 -> "1:05", like the desktop app. */
private fun formatDuration(seconds: Int): String {
    if (seconds <= 0) return ""
    val h = seconds / 3600
    val m = seconds % 3600 / 60
    val s = seconds % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
}
