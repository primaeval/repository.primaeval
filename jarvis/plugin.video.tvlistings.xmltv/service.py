ADDON = "plugin.video.tvlistings.xmltv"
import main
from datetime import datetime,timedelta
import time
import xbmcaddon
import xbmc

xbmcaddon.Addon(ADDON).setSetting('playing_channel','')
xbmcaddon.Addon(ADDON).setSetting('playing_title','')
xbmcaddon.Addon(ADDON).setSetting('playing_start','')
main.refresh_reminders()
monitor = xbmc.Monitor()
while not monitor.abortRequested():
    try:
        reload = xbmcaddon.Addon(ADDON).getSetting('xml_reload_timer')
    except:
        reload = 'false'
    if (reload == 'true'):
        dt = datetime.now()
        try:
            xmltv_timer_last = int(xbmcaddon.Addon(ADDON).getSetting('xmltv_timer_last'))
        except:
            xmltv_timer_last = 0
        now_seconds = int(time.mktime(dt.timetuple()))
        timeout = False
        if xmltv_timer_last + 25*3600 < now_seconds:
            timeout = True
        else:
            hour = xbmcaddon.Addon(ADDON).getSetting('xml_reload_hour')
            if xmltv_timer_last + 1*3600 < now_seconds: # only once a day
                if dt.hour == hour:
                    timeout = True
        if timeout:
            xbmcaddon.Addon(ADDON).setSetting('xml_reload','true')
            main.xml_channels()
            xbmcaddon.Addon(ADDON).setSetting('ini_reload','true')
            main.store_channels()
            now = int(time.mktime(dt.timetuple()))
            xbmcaddon.Addon(ADDON).setSetting("xmltv_timer_last",str(now))
    wait_time = 60
    if monitor.waitForAbort(wait_time):
        break
