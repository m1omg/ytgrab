package dev.ytgrab.app

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.ClipboardManager
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.core.content.ContextCompat
import dev.ytgrab.app.ui.MainScreen
import dev.ytgrab.app.ui.YtgrabTheme

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    // A download waiting for the storage permission (Android 7-9 only).
    private var pending: DownloadRequest? = null

    private val storagePermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            val request = pending
            pending = null
            if (granted && request != null) startDownload(request)
            else viewModel.message = getString(R.string.storage_permission)
        }

    // Asked for once; downloads work without it, just without a notification.
    private val notificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        if (savedInstanceState == null) handle(intent)
        setContent {
            YtgrabTheme {
                MainScreen(
                    viewModel = viewModel,
                    onPaste = ::paste,
                    onDownload = ::download,
                    onCancel = { DownloadService.requestCancel(this) },
                    onOpen = ::open,
                    onShare = ::share,
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    private fun handle(intent: Intent?) {
        if (intent?.action == Intent.ACTION_SEND) {
            intent.getStringExtra(Intent.EXTRA_TEXT)?.let(viewModel::onShared)
        }
    }

    private fun paste() {
        val clipboard = getSystemService(ClipboardManager::class.java)
        val text = clipboard.primaryClip?.takeIf { it.itemCount > 0 }
            ?.getItemAt(0)?.coerceToText(this)?.toString()?.trim()
        if (text.isNullOrEmpty()) {
            Toast.makeText(this, R.string.clipboard_empty, Toast.LENGTH_SHORT).show()
        } else {
            viewModel.onShared(text)
        }
    }

    private fun download() {
        if (Downloads.isRunning) {
            Toast.makeText(this, R.string.busy, Toast.LENGTH_SHORT).show()
            return
        }
        val request = viewModel.request() ?: return
        viewModel.message = null
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            !granted(Manifest.permission.POST_NOTIFICATIONS)
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q &&
            !granted(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        ) {
            pending = request
            storagePermission.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE)
            return
        }
        startDownload(request)
    }

    private fun startDownload(request: DownloadRequest) {
        val intent = request.putInto(Intent(this, DownloadService::class.java).setAction(DownloadService.ACTION_START))
        ContextCompat.startForegroundService(this, intent)
    }

    private fun granted(permission: String) =
        ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED

    private fun open(file: SavedFile) {
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(file.uri, file.mime)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        try {
            startActivity(intent)
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(this, R.string.no_app, Toast.LENGTH_LONG).show()
        }
    }

    private fun share(file: SavedFile) {
        val intent = Intent(Intent.ACTION_SEND)
            .setType(file.mime)
            .putExtra(Intent.EXTRA_STREAM, file.uri)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        startActivity(Intent.createChooser(intent, null))
    }
}
