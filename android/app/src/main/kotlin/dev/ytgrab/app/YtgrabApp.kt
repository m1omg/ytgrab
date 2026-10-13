package dev.ytgrab.app

import android.app.Application

class YtgrabApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Notifications.createChannel(this)
    }
}
