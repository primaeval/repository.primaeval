from xbmcswift2 import Plugin
from xbmcswift2 import actions
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import re

import requests

from datetime import datetime,timedelta
import time
import urllib
import HTMLParser
import xbmcplugin
import xml.etree.ElementTree as ET
import sqlite3
import os
import shutil
from rpc import RPC
from types import *

plugin = Plugin()
big_list_view = False

def log2(v):
    xbmc.log(repr(v))

def log(v):
    xbmc.log(re.sub(',',',\n',repr(v)))

def get_icon_path(icon_name):
    addon_path = xbmcaddon.Addon().getAddonInfo("path")
    return os.path.join(addon_path, 'resources', 'img', icon_name+".png")


def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]",'',label)
    label = re.sub(r"\[/?COLOR.*?\]",'',label)
    return label

def get_tvdb_id(name):
    tvdb_url = "http://thetvdb.com//api/GetSeries.php?seriesname=%s" % name
    try:
        r = requests.get(tvdb_url)
    except:
        return ''
    tvdb_html = r.text
    tvdb_id = ''
    tvdb_match = re.search(r'<seriesid>(.*?)</seriesid>', tvdb_html, flags=(re.DOTALL | re.MULTILINE))
    if tvdb_match:
        tvdb_id = tvdb_match.group(1)
    return tvdb_id


@plugin.route('/clear_addon_paths')
def clear_addon_paths():
    conn = get_conn()
    conn.execute('UPDATE channels SET path=NULL')
    conn.execute('DROP TABLE IF EXISTS addon_paths')
    conn.commit()
    create_database_tables()
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Clear Addon Paths")


@plugin.route('/clear_addons')
def clear_addons():
    conn = get_conn()
    conn.execute('UPDATE channels SET path=NULL')
    conn.execute('DROP TABLE IF EXISTS addons')
    conn.commit()
    create_database_tables()
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Clear Addons")


@plugin.route('/drop_channels')
def drop_channels():
    conn = get_conn()
    conn.execute('DROP TABLE IF EXISTS channels')
    conn.commit()
    create_database_tables()


@plugin.route('/clear_channels')
def clear_channels():
    conn = get_conn()
    conn.execute('UPDATE channels SET path=NULL')
    conn.commit()
    create_database_tables()
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Clear Channels")


@plugin.route('/export_channels')
def export_channels():
    folder = plugin.get_setting('export_ini_folder')
    if not folder:
        folder = 'special://profile/addon_data/plugin.video.tvlistings.xmltv'
    file_name = os.path.join(xbmc.translatePath(folder),'plugin.video.tvlistings.xmltv.ini')
    f = xbmcvfs.File(file_name,'w')
    if not f:
        dialog = xbmcgui.Dialog()
        dialog.notification("TV Listings (xmltv)","Error: could not create file")
    write_str = "# WARNING Make a copy of this file.\n# It will be overwritten on the next channel export.\n\n[plugin.video.tvlistings.xmltv]\n"
    f.write(write_str.encode("utf8"))

    items = []

    conn = get_conn()
    c = conn.cursor()

    c.execute('SELECT id,path FROM channels')
    channel_ids = {}
    for row in c:
        channel_id = row['id']
        channel_id = re.sub(r'[:=]',' ',channel_id)
        path = row['path']
        if channel_id in channel_ids:
            channel_id = "%s." %  channel_id
        channel_ids[channel_id] = channel_id
        if not path:
            path = 'nothing'
        write_str = "%s=%s\n" % (channel_id,path)
        f.write(write_str.encode("utf8"))

    c.execute('SELECT DISTINCT addon FROM addons')
    addons = [row["addon"] for row in c]

    for addon in addons:
        write_str = "[%s]\n" % (addon)
        f.write(write_str.encode("utf8"))
        c.execute('SELECT name,path FROM addons WHERE addon=?', [addon])
        channel_names = {}
        for row in c:
            channel_name = row['name']
            if channel_name.startswith(' '):
                continue
            channel_name = re.sub(r'[:=]',' ',channel_name)
            if channel_name in channel_names:
                channel_name = "%s." %  channel_name
            channel_names[channel_name] = channel_name
            path = row['path']
            if not path:
                path = 'nothing'
            write_str = "%s=%s\n" % (channel_name,path)
            f.write(write_str.encode("utf8"))
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Export Channels")
    c.close()
    return items


@plugin.route('/channel_list')
def channel_list():
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM channels')
    items = []
    for row in c:
        channel_id = row['id']
        channel_name = row['name']
        img_url = row['icon']
        path = row['path']


        if path:
            cc = conn.cursor()
            cc.execute('SELECT addon FROM addons WHERE path=?', [path])
            row = cc.fetchone()
            addon_id = row["addon"]
            (addon_name,addon_icon) = get_addon_info(addon_id)

            label = "[COLOR gold][B]%s[/B][/COLOR] [COLOR seagreen][B]%s[/B][/COLOR]" % (
            channel_name,addon_name)
            item = {'label':label,'icon':img_url,'thumbnail':img_url}
            item['path'] = plugin.url_for('play_media',path=path)
            item['is_playable'] = False

            choose_url = plugin.url_for('channel_remap_all', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), channel_play=True)
            search_url = plugin.url_for(search_addons,channel_name=channel_name.encode("utf8"))
            item['context_menu'] = [
            ('[COLOR seagreen]Search Channel[/COLOR]', actions.update_view(search_url)),

            ('[COLOR crimson]Default Shortcut[/COLOR]', actions.update_view(choose_url))]
            items.append(item)
    c.close()
    sorted_items = sorted(items, key=lambda item: item['label'])
    return sorted_items


@plugin.route('/channel_remap')
def channel_remap():
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()

    c.execute('SELECT addon, path FROM addons')
    addons = dict([[row["path"], (row["addon"])] for row in c])

    c.execute('SELECT * FROM channels')
    items = []
    for row in c:
        channel_id = row['id']
        channel_name = row['name']
        img_url = row['icon']
        path = row['path']
        if path in addons:
            (addon_id) = addons[path]
            (addon_name,addon_icon) = get_addon_info(addon_id)

            addon_label = " [COLOR seagreen][B]%s[/B][/COLOR]" % addon_name
            img_url = addon_icon
        else:
            addon_label = ""

        if path:
            label = "[COLOR crimson][B]%s[/B][/COLOR]%s" % (channel_name,addon_label)
        else:
            label = "[COLOR gold][B]%s[/B][/COLOR]%s" % (channel_name,addon_label)
        item = {'label':label,'thumbnail':img_url}
        item['path'] = plugin.url_for('channel_remap_all', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), channel_play=True)
        items.append(item)
    c.close()
    sorted_items = sorted(items, key=lambda item: remove_formatting(item['label']))
    return sorted_items


@plugin.route('/channel_remap_addons/<channel_id>/<channel_name>')
def channel_remap_addons(channel_id,channel_name):
    global big_list_view
    big_list_view = True
    items = []

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT DISTINCT addon FROM addons')
    addons = [row["addon"] for row in c]
    icon = ''
    item = {
    'label': '[COLOR crimson][B]%s[/B][/COLOR]' % ("Search Addons"),
    'path': plugin.url_for(channel_remap_search, channel_id=channel_id,channel_name=channel_name),
    'thumbnail': get_icon_path('search'),
    'is_playable': False,
    }

    for addon_id in sorted(addons):
        try:
            addon = xbmcaddon.Addon(addon_id)
            if addon:
                icon = addon.getAddonInfo('icon')
                item = {
                'label': '[COLOR seagreen][B]%s[/B][/COLOR]' % (remove_formatting(addon.getAddonInfo('name'))),
                'path': plugin.url_for(channel_remap_streams, addon_id=addon_id,channel_id=channel_id,channel_name=channel_name),
                'thumbnail': icon,
                'icon': icon,
                'is_playable': False,
                }
                items.append(item)
        except:
            pass
    return items


@plugin.route('/search_addons/<channel_name>')
def search_addons(channel_name):
    global big_list_view
    big_list_view = True
    if channel_name == 'none':
        dialog = xbmcgui.Dialog()
        channel_name = dialog.input('Search for channel?', type=xbmcgui.INPUT_ALPHANUM)
    if not channel_name:
        return

    items = []
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM addons WHERE REPLACE(LOWER(name), ' ', '') LIKE REPLACE(LOWER(?), ' ', '') ORDER BY addon, name", ['%'+channel_name.decode("utf8")+'%'])
    for row in c:
        path = row["path"]
        stream_name = row["name"]
        icon = row["icon"]

        addon_id = row["addon"]
        (addon_name,addon_icon) = get_addon_info(addon_id)
        if not addon_name:
            continue

        label = "[COLOR gold][B]%s[/B][/COLOR] [COLOR seagreen][B]%s[/B][/COLOR]" % (
        stream_name,addon_name)
        item = {
        'label': label,
        'path': plugin.url_for("play_media",path=path),
        'thumbnail': addon_icon,
        'is_playable': False
        }

        items.append(item)

    return items


@plugin.route('/play_media/<path>/')
def play_media(path):
    cmd = "PlayMedia(%s)" % path
    xbmc.executebuiltin(cmd)



@plugin.route('/channel_remap_search/<channel_id>/<channel_name>')
def channel_remap_search(channel_id,channel_name):
    dialog = xbmcgui.Dialog()
    channel_name = dialog.input('Search for channel?', type=xbmcgui.INPUT_ALPHANUM)
    if not channel_name:
        return
    return channel_remap_all(channel_id,channel_name)


@plugin.route('/channel_remap_all/<channel_id>/<channel_name>/<channel_play>')
def channel_remap_all(channel_id,channel_name,channel_play):
    global big_list_view
    big_list_view = True

    items = []

    img_url = get_icon_path('search')
    label = "[COLOR gold][B]%s[/B][/COLOR] [COLOR cornflowerblue][B]%s[/B][/COLOR]" % (channel_name, 'All Streams')
    item = {'label':label,'thumbnail':img_url}
    item['path'] = plugin.url_for('channel_remap_addons', channel_id=channel_id, channel_name=channel_name)
    items.append(item)
    label = "[COLOR gold][B]%s[/B][/COLOR] [COLOR white][B]%s[/B][/COLOR]" % (channel_name, 'Reset Channel')
    item = {'label':label,'thumbnail':get_icon_path('settings')}
    item['path'] = plugin.url_for('reset_channel', channel_id=channel_id)
    items.append(item)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM channels WHERE id=?", [channel_id.decode("utf8")])
    row = c.fetchone()
    channel_path = row["path"]
    channel_icon = row["icon"]
    c.execute("SELECT * FROM addons WHERE REPLACE(LOWER(name), ' ', '') LIKE REPLACE(LOWER(?), ' ', '') ORDER BY addon, name", ['%'+channel_name.decode("utf8")+'%'])

    for row in c:
        addon_id = row["addon"]
        stream_name = row["name"]
        path = row["path"]
        icon = row["icon"]


        (addon_name,addon_icon) = get_addon_info(addon_id)
        if not addon_name:
            continue
        if channel_path == path:
            label = '[COLOR gold][B]%s[/B][/COLOR] [COLOR crimson][B]%s[/B][/COLOR]' % (stream_name, addon_name)
        else:
            label = '[COLOR gold][B]%s[/B][/COLOR] [COLOR seagreen][B]%s[/B][/COLOR]' % (stream_name, addon_name)
        item = {
        'label': label,
        'path': plugin.url_for(channel_remap_stream, addon_id=addon_id, channel_id=channel_id, channel_name=channel_name, stream_name=stream_name.encode("utf8")),
        'thumbnail': addon_icon,
        'icon': addon_icon,
        'is_playable': False,
        }

        url = plugin.url_for('play_media', path=path)
        item['context_menu'] = [('[COLOR gold]Play Channel[/COLOR]', actions.update_view(url))]
        items.append(item)

    if channel_play == "True":
        if channel_path:
            item = {'label':"[COLOR gold]%s[/COLOR] [COLOR crimson]%s[/COLOR]" % (channel_name,'Play'),
            'path': plugin.url_for('play_media', path=channel_path),
            'thumbnail':channel_icon,
            'is_playable':False}


    return items


@plugin.route('/channel_remap_streams/<addon_id>/<channel_id>/<channel_name>')
def channel_remap_streams(addon_id,channel_id,channel_name):
    global big_list_view
    big_list_view = True

    (addon_name,addon_icon) = get_addon_info(addon_id)

    items = []

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT * FROM channels WHERE id=?", [channel_id.decode("utf8")])
    row = c.fetchone()
    channel_path = row["path"]

    c.execute('SELECT * FROM addons WHERE addon=?', [addon_id])
    streams = dict([row["path"],[row["name"], row["icon"]]] for row in c)

    for path in sorted(streams):
        (stream_name,icon) = streams[path]
        if channel_path == path:
            label = '[COLOR gold][B]%s[/B][/COLOR] [COLOR crimson][B]%s[/B][/COLOR]' % (stream_name, addon_name)
        else:
            label = '[COLOR gold][B]%s[/B][/COLOR] [COLOR seagreen][B]%s[/B][/COLOR]' % (stream_name, addon_name)

        item = {
        'label': label,
        'path': plugin.url_for(channel_remap_stream, addon_id=addon_id, channel_id=channel_id, channel_name=channel_name, stream_name=stream_name.encode("utf8")),
        'thumbnail': icon,
        'icon': icon,
        'is_playable': False,
        }

        url = plugin.url_for('play_media', path=path)
        item['context_menu'] = [('[COLOR gold]Play Channel[/COLOR]', actions.update_view(url))]
        items.append(item)

    sorted_items = sorted(items, key=lambda item: item['label'])
    return sorted_items


@plugin.route('/rename_shortcut/<addon_id>/<stream_name>/<path>')
def rename_shortcut(addon_id,stream_name,path):
    dialog = xbmcgui.Dialog()
    new_stream_name = dialog.input('Enter new Shortcut Name', stream_name, type=xbmcgui.INPUT_ALPHANUM)
    if not new_stream_name:
        return
    path = urllib.unquote(path)
    conn = get_conn()
    conn.execute('UPDATE addons SET name=? WHERE path=? AND addon=?', [new_stream_name,path,addon_id])
    conn.commit()


@plugin.route('/reset_channel/<channel_id>')
def reset_channel(channel_id):
    conn = get_conn()
    conn.execute('UPDATE channels SET path=NULL WHERE id=?', [channel_id.decode("utf8")])
    conn.commit()


@plugin.route('/channel_remap_stream/<addon_id>/<channel_id>/<channel_name>/<stream_name>')
def channel_remap_stream(addon_id,channel_id,channel_name,stream_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT path, icon FROM addons WHERE addon=? AND name=?', [addon_id, stream_name.decode("utf8")])
    row = c.fetchone()
    path = row["path"]
    icon = row["icon"]

    if icon:
        c.execute('UPDATE channels SET path=?, icon=? WHERE id=?', [path,icon,channel_id.decode("utf8")])
    else:
        c.execute('UPDATE channels SET path=? WHERE id=?', [path,channel_id.decode("utf8")])
    conn.commit()
    if plugin.get_setting("refresh") == 'true':
        xbmc.executebuiltin('Container.Refresh')



@plugin.route('/play_channel/<channel_id>/<title>/<start>')
def play_channel(channel_id,title,start):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM channels WHERE id=?", [channel_id.decode("utf8")])
    row = c.fetchone()
    channel_path = row["path"]

    plugin.set_setting('playing_channel',channel_id)
    plugin.set_setting('playing_title',title)
    plugin.set_setting('playing_start',start)

    play_media(channel_path)


@plugin.route('/stop_playing/<channel_id>/<title>/<start>')
def stop_playing(channel_id,title,start):
    if plugin.get_setting('playing_channel') != channel_id:
        return
    elif plugin.get_setting('playing_start') != start:
        return
    plugin.set_setting('playing_channel','')
    plugin.set_setting('playing_title','')
    plugin.set_setting('playing_start','')
    if plugin.get_setting("refresh") == 'true':
        xbmc.executebuiltin('PlayerControl(Stop)')


def get_conn():
    profilePath = xbmc.translatePath(plugin.addon.getAddonInfo('profile'))
    if not os.path.exists(profilePath):
        os.makedirs(profilePath)
    databasePath = os.path.join(profilePath, 'source.db')

    conn = sqlite3.connect(databasePath, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    return conn


@plugin.route('/clear_reminders')
def clear_reminders():
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute('SELECT * FROM remind')
        for row in c:
            channel_id = row['channel']
            start = row['start']
            title = row['title']
            xbmc.executebuiltin('CancelAlarm(%s,False)' % (channel_id+title+str(start)))

        c.execute('SELECT * FROM watch')
        for row in c:
            channel_id = row['channel']
            start = row['start']
            title = row['title']
            xbmc.executebuiltin('CancelAlarm(%s-start,False)' % (channel_id+title+str(start)))
            xbmc.executebuiltin('CancelAlarm(%s-stop,False)' % (channel_id+title+str(start)))
    except:
        pass

    c.execute('DELETE FROM remind')
    c.execute('DELETE FROM watch')
    conn.commit()
    conn.close()
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Clear Reminders")


@plugin.route('/refresh_reminders')
def refresh_reminders():
    notify = False
    try:
        conn = get_conn()
        c = conn.cursor()

        c.execute('SELECT * FROM remind')
        for row in c:
            notify = True
            start = row['start']
            t = datetime.fromtimestamp(float(start)) - datetime.now()
            timeToNotification = ((t.days * 86400) + t.seconds) / 60
            icon = ''
            description = "%s: %s" % (row['channel'],row['title'])
            xbmc.executebuiltin('AlarmClock(%s,Notification(%s,%s,10000,%s),%d)' %
                (row['channel']+row['title']+str(start), row['title'], description, icon, timeToNotification - int(plugin.get_setting('remind_before'))))

        c.execute('SELECT * FROM watch')
        for row in c:
            notify = True
            channel_id = row['channel']
            start = row['start']
            stop = row['stop']
            title = row['title']
            t = datetime.fromtimestamp(float(start)) - datetime.now()
            timeToNotification = ((t.days * 86400) + t.seconds) / 60
            command = 'AlarmClock(%s-start,PlayMedia(plugin://plugin.video.tvlistings.xmltv/play_channel/%s/%s/%s),%d,False)' % (
            channel_id+title+str(start), channel_id, title, start, timeToNotification - int(plugin.get_setting('remind_before')))
            xbmc.executebuiltin(command.encode("utf8"))
            if plugin.get_setting('watch_and_stop') == 'true':
                t = datetime.fromtimestamp(float(stop)) - datetime.now()
                timeToNotification = ((t.days * 86400) + t.seconds) / 60
                command = 'AlarmClock(%s-stop,PlayMedia(plugin://plugin.video.tvlistings.xmltv/stop_playing/%s/%s/%s),%d,True)' % (
                channel_id+title+str(start), channel_id, title, start, timeToNotification + int(plugin.get_setting('remind_after')))
                xbmc.executebuiltin(command.encode("utf8"))

        conn.commit()
        conn.close()
    except:
        pass
    #if notify:
    #    dialog = xbmcgui.Dialog()
    #   dialog.notification("TV Listings (xmltv)","Done: Refresh Reminders",sound=False)


@plugin.route('/remind/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def remind(channel_id,channel_name,title,season,episode,start,stop):
    t = datetime.fromtimestamp(float(start)) - datetime.now()
    timeToNotification = ((t.days * 86400) + t.seconds) / 60
    icon = ''
    description = "%s: %s" % (channel_name,title)
    xbmc.executebuiltin('AlarmClock(%s,Notification(%s,%s,10000,%s),%d)' %
        (channel_id+title+str(start), title, description, icon, timeToNotification - int(plugin.get_setting('remind_before'))))

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id.decode("utf8"),start])
    row = c.fetchone()
    c.execute("INSERT OR REPLACE INTO remind(channel ,title , sub_title , start , stop, date, description , series , episode , categories) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    [row['channel'] ,row['title'] , row['sub_title'] , row['start'] , row['stop'], row['date'], row['description'] , row['series'] , row['episode'] , row['categories']])
    conn.commit()
    conn.close()
    if plugin.get_setting("refresh") == 'true':
        xbmc.executebuiltin('Container.Refresh')
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification("TV Listings (xmltv)","Done: Remind")


@plugin.route('/watch/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def watch(channel_id,channel_name,title,season,episode,start,stop):
    t = datetime.fromtimestamp(float(start)) - datetime.now()
    timeToNotification = ((t.days * 86400) + t.seconds) / 60
    xbmc.executebuiltin('AlarmClock(%s-start,PlayMedia(plugin://plugin.video.tvlistings.xmltv/play_channel/%s/%s/%s),%d,False)' %
        (channel_id+title+str(start), channel_id, title, start, timeToNotification - int(plugin.get_setting('remind_before'))))

    #TODO check for overlapping times
    if plugin.get_setting('watch_and_stop') == 'true':
        t = datetime.fromtimestamp(float(stop)) - datetime.now()
        timeToNotification = ((t.days * 86400) + t.seconds) / 60
        xbmc.executebuiltin('AlarmClock(%s-stop,PlayMedia(plugin://plugin.video.tvlistings.xmltv/stop_playing/%s/%s/%s),%d,True)' %
            (channel_id+title+str(start), channel_id, title, start, timeToNotification + int(plugin.get_setting('remind_after'))))

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id.decode("utf8"),start])
    row = c.fetchone()
    c.execute("INSERT OR REPLACE INTO watch(channel ,title , sub_title , start , stop, date, description , series , episode , categories) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    [row['channel'] ,row['title'] , row['sub_title'] , row['start'] , row['stop'], row['date'], row['description'] , row['series'] , row['episode'] , row['categories']])
    conn.commit()
    conn.close()
    if plugin.get_setting("refresh") == 'true':
        xbmc.executebuiltin('Container.Refresh')
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification("TV Listings (xmltv)","Done: Watch")


@plugin.route('/cancel_remind/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def cancel_remind(channel_id,channel_name,title,season,episode,start,stop):
    t = datetime.fromtimestamp(float(start)) - datetime.now()
    timeToNotification = ((t.days * 86400) + t.seconds) / 60
    icon = ''
    description = "%s: %s" % (channel_name,title)
    xbmc.executebuiltin('CancelAlarm(%s,False)' % (channel_id+title+str(start)))

    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM remind WHERE channel=? AND start=?', [channel_id.decode("utf8"),start])

    conn.commit()
    conn.close()

    if plugin.get_setting("refresh") == 'true':
        xbmc.executebuiltin('Container.Refresh')
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification("TV Listings (xmltv)","Done: Cancel Remind")


@plugin.route('/cancel_watch/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def cancel_watch(channel_id,channel_name,title,season,episode,start,stop):
    t = datetime.fromtimestamp(float(start)) - datetime.now()
    timeToNotification = ((t.days * 86400) + t.seconds) / 60
    icon = ''
    description = "%s: %s" % (channel_name,title)

    xbmc.executebuiltin('CancelAlarm(%s-start,False)' % (channel_id+title+str(start)))
    xbmc.executebuiltin('CancelAlarm(%s-stop,False)' % (channel_id+title+str(start)))

    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM watch WHERE channel=? AND start=?', [channel_id.decode("utf8"),start])
    conn.commit()
    conn.close()

    if plugin.get_setting("refresh") == 'true':
        xbmc.executebuiltin('Container.Refresh')
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification("TV Listings (xmltv)","Done: Cancel Watch")


@plugin.route('/play/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def play(channel_id,channel_name,title,season,episode,start,stop):
    global big_list_view
    big_list_view = True
    channel_items = channel(channel_id,channel_name)
    items = []
    tvdb_id = ''
    if int(season) > 0 and int(episode) > 0:
        tvdb_id = get_tvdb_id(title)
    try:
        addon = xbmcaddon.Addon('plugin.video.meta')
        meta_icon = addon.getAddonInfo('icon')
    except:
        meta_icon = ""
    if tvdb_id:
        if meta_icon:
            if season and episode:
                meta_url = "plugin://plugin.video.meta/tv/play/%s/%s/%s/%s" % (tvdb_id,season,episode,'select')
                items.append({
                'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR crimson][B]S%sE%s[/B][/COLOR] [COLOR seagreen][B]Meta episode[/B][/COLOR]' % (title,season,episode),
                'path': meta_url,
                'thumbnail': meta_icon,
                'icon': meta_icon,
                'is_playable': True,
                 })
            if season:
                meta_url = "plugin://plugin.video.meta/tv/tvdb/%s/%s" % (tvdb_id,season)
                items.append({
                'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR crimson][B]S%s[/B][/COLOR] [COLOR seagreen][B]Meta season[/B][/COLOR]' % (title,season),
                'path': meta_url,
                'thumbnail': meta_icon,
                'icon': meta_icon,
                'is_playable': False,
                 })
            meta_url = "plugin://plugin.video.meta/tv/tvdb/%s" % (tvdb_id)
            items.append({
            'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR seagreen][B]Meta TV search[/B][/COLOR]' % (title),
            'path': meta_url,
            'thumbnail': meta_icon,
            'icon': meta_icon,
            'is_playable': False,
             })
        try:
            addon = xbmcaddon.Addon('plugin.video.sickrage')
            sick_icon =  addon.getAddonInfo('icon')
            if addon:
                items.append({
                'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR gold][B]SickRage[/B][/COLOR]' % (title),
                'path':"plugin://plugin.video.sickrage?action=addshow&&show_name=%s" % (title),
                'thumbnail': sick_icon,
                'icon': sick_icon,
                })
        except:
            pass
    else:
        match = re.search(r'(.*?)\(([0-9]*)\)$',title)
        if match:
            movie = match.group(1)
            year =  match.group(2) #TODO: Meta doesn't support year yet
            if meta_icon:
                meta_url = "plugin://plugin.video.meta/movies/search_term/%s/1" % (movie)
                items.append({
                'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR seagreen][B]Meta movie[/B][/COLOR]' % (title),
                'path': meta_url,
                'thumbnail': meta_icon,
                'icon': meta_icon,
                'is_playable': False,
                 })
            try:
                addon = xbmcaddon.Addon('plugin.video.couchpotato_manager')
                couch_icon =  addon.getAddonInfo('icon')
                if addon:
                    items.append({
                    'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR gold][B]CouchPotato[/B][/COLOR]' % (title),
                    'path':"plugin://plugin.video.couchpotato_manager/movies/add/?title=%s" % (title),
                    'thumbnail': couch_icon,
                    'icon': couch_icon,
                    })
            except:
                pass
        else:
            if meta_icon:
                meta_url = "plugin://plugin.video.meta/tv/search_term/%s/1" % (title)
                items.append({
                'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR seagreen][B]Meta TV search[/B][/COLOR]' % (title),
                'path': meta_url,
                'thumbnail': meta_icon,
                'icon': meta_icon,
                'is_playable': False,
                 })
                meta_url = "plugin://plugin.video.meta/movies/search_term/%s/1" % (title)
                items.append({
                'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR seagreen][B]Meta movie search[/B][/COLOR]' % (title),
                'path': meta_url,
                'thumbnail': meta_icon,
                'icon': meta_icon,
                'is_playable': False,
                 })
            try:
                addon = xbmcaddon.Addon('plugin.video.sickrage')
                sick_icon =  addon.getAddonInfo('icon')
                if addon:
                    items.append({
                    'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR gold][B]SickRage[/B][/COLOR]' % (title),
                    'path':"plugin://plugin.video.sickrage?action=addshow&&show_name=%s" % (title),
                    'thumbnail': sick_icon,
                    'icon': sick_icon,
                    })
            except:
                pass

    try:
        addon = xbmcaddon.Addon('plugin.program.super.favourites')
        sf_icon =  addon.getAddonInfo('icon')
        if addon:
            items.append({
            'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR seagreen][B]iSearch[/B][/COLOR]' % (title),
            'path':"plugin://plugin.program.super.favourites?mode=0&keyword=%s" % (urllib.quote_plus(title)),
            'thumbnail': sf_icon,
            'icon': sf_icon,
            })
    except:
        pass

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM remind WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    remind = [row['start'] for row in c]
    c.execute('SELECT * FROM watch WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    watch = [row['start'] for row in c]
    #TODO deal with disabled addons
    clock_icon = get_icon_path('alarm')
    if not int(start) in remind:
        items.append({
        'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR crimson][B]Remind[/B][/COLOR]' % (title),
        'path':plugin.url_for('remind', channel_id=channel_id, channel_name=channel_name,title=title, season=season, episode=episode, start=start, stop=stop),
        'thumbnail': clock_icon,
        'icon': clock_icon,
        })
    else:
        items.append({
        'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR crimson][B]Cancel Remind[/B][/COLOR]' % (title),
        'path':plugin.url_for('cancel_remind', channel_id=channel_id, channel_name=channel_name,title=title, season=season, episode=episode, start=start, stop=stop),
        'thumbnail': clock_icon,
        'icon': clock_icon,
        })

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT path FROM channels WHERE id=?', [channel_id.decode("utf8")])
    row = c.fetchone()
    path = row["path"]
    if path:
        if not int(start) in watch:
            items.append({
            'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR cornflowerblue][B]Watch[/B][/COLOR]' % (title),
            'path':plugin.url_for('watch', channel_id=channel_id, channel_name=channel_name,title=title, season=season, episode=episode, start=start, stop=stop),
            'thumbnail': clock_icon,
            'icon': clock_icon,
            })
        else:
            items.append({
            'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR cornflowerblue][B]Cancel Watch[/B][/COLOR]' % (title),
            'path':plugin.url_for('cancel_watch', channel_id=channel_id, channel_name=channel_name,title=title, season=season, episode=episode, start=start, stop=stop),
            'thumbnail': clock_icon,
            'icon': clock_icon,
            })

    items.extend(channel_items)
    return items



@plugin.route('/channel/<channel_id>/<channel_name>')
def channel(channel_id,channel_name):
    global big_list_view
    big_list_view = True

    items = []

    addon = xbmcaddon.Addon()
    addon_icon = addon.getAddonInfo('icon')
    addon_name = remove_formatting(addon.getAddonInfo('name'))

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM channels WHERE id=?', [channel_id.decode("utf8")])
    row = c.fetchone()
    path = row["path"]
    icon = row["icon"]

    choose = False
    if path:
        c.execute('SELECT addon FROM addons WHERE path=?', [path])
        row = c.fetchone()
        addon = row["addon"]
        (addon_name,addon_icon) = get_addon_info(addon)
        if addon_name:
            label = "[COLOR gold][B]%s[/B][/COLOR] [COLOR seagreen][B]%s[/B] [COLOR white][B]Play[/B][/COLOR]" % (
            channel_name,addon_name)
            item = {'label':label,'thumbnail':addon_icon}
            item['path'] = plugin.url_for("play_media",path=path)
            item['is_playable'] = False
            choose_url = plugin.url_for('channel_remap_all', channel_id=channel_id, channel_name=channel_name, channel_play=True)
            item['context_menu'] = [('[COLOR crimson]Default Shortcut[/COLOR]', actions.update_view(choose_url))]
            items.append(item)
        else:
            choose = True
    else:
        choose = True
    if choose:
        label = "[COLOR gold][B]%s[/B][/COLOR] [COLOR white][B]Choose Player[/B][/COLOR]" % (channel_name)
        item = {'label':label,'icon':icon,'thumbnail':get_icon_path('search')}
        item['path'] = plugin.url_for('channel_remap_all', channel_id=channel_id, channel_name=channel_name, channel_play=True)
        items.append(item)
    item = {'label':"[COLOR gold][B]%s[/B][/COLOR] [COLOR seagreen][B]%s[/B][/COLOR]" % (channel_name,'Search'),
        'path': plugin.url_for(search_addons,channel_name=channel_name),
        'thumbnail':icon,
        'is_playable':False}
    items.append(item)
    return items



@plugin.route('/addon_streams')
def addon_streams():
    global big_list_view
    big_list_view = True
    items = []

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT DISTINCT addon FROM addons')
    addons = [row["addon"] for row in c]

    icon = ''
    for addon_id in sorted(addons):
        try:
            addon = xbmcaddon.Addon(addon_id)
            if addon:
                icon = addon.getAddonInfo('icon')
                item = {
                'label': '[COLOR seagreen][B]%s[/B][/COLOR]' % (remove_formatting(addon.getAddonInfo('name'))),
                'path': plugin.url_for(streams, addon_id=addon_id),
                'thumbnail': icon,
                'icon': icon,
                'is_playable': False,
                }
                url = plugin.url_for('addon_streams_to_channels', addon_id=addon_id)
                item['context_menu'] = [('[COLOR gold]Set as Channels[/COLOR]', actions.update_view(url))]
                items.append(item)
        except:
            pass
    sorted_items = sorted(items, key=lambda item: item['label'].lower())
    items = []
    item = {
    'label': '[COLOR crimson][B]%s[/B][/COLOR]' % ("Search Addons"),
    'path': plugin.url_for(search_addons, channel_name='none'),
    'thumbnail': get_icon_path('search'),
    'is_playable': False,
    }
    items.append(item)
    item = {
    'label': '[COLOR gold][B]%s[/B][/COLOR]' % ("Refresh Addon Shortcuts"),
    'path': plugin.url_for(reload_addon_paths),
    'thumbnail': get_icon_path('settings'),
    'is_playable': False,
    }
    items.append(item)
    items= items + sorted_items
    return items



@plugin.route('/addon_streams_to_channels/<addon_id>')
def addon_streams_to_channels(addon_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM addons WHERE addon=?', [addon_id])
    channels = dict((row['name'], (row['path'], row['icon'])) for row in c)

    for channel_name in channels:
        (path, icon) = channels[channel_name]
        channel_name = re.sub(r'\(.*?\)$','',channel_name).strip()
        if icon:
            c.execute('UPDATE channels SET path=?, icon=? WHERE name=?', [path, icon, channel_name])
        else:
            c.execute('UPDATE channels SET path=? WHERE name=?', [path, channel_name])

    conn.commit()
    conn.close()
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Addon Shortcuts to Default Shortcuts")



@plugin.route('/streams/<addon_id>')
def streams(addon_id):
    global big_list_view
    big_list_view = True

    (addon_name,addon_icon) = get_addon_info(addon_id)

    items = []

    item = {'label':'[COLOR crimson][B]Use All as Default Shortcuts[/B][/COLOR]',
        'path':plugin.url_for('addon_streams_to_channels', addon_id=addon_id),
        'thumbnail':addon_icon,
        'is_playable':False}
    items.append(item)

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM addons WHERE addon=?', [addon_id])

    for row in c:
        path = row["path"]
        stream_name = row["name"]
        icon = row["icon"]

        addon_id = row["addon"]

        label = "[COLOR gold][B]%s[/B][/COLOR] [COLOR seagreen][B]%s[/B][/COLOR]" % (
        stream_name,addon_name)
        item = {
        'label': label,
        'path': plugin.url_for("play_media",path=path),
        'thumbnail': icon,
        'icon': icon,
        'is_playable': False,
        }
        remap_url = plugin.url_for('stream_remap',stream_name=stream_name.encode("utf8"),path=path,icon=icon)
        url = plugin.url_for('play_media', path=path)

        item['context_menu'] = [
        ('[COLOR gold]Play Channel[/COLOR]', actions.update_view(url)),
        ('[COLOR crimson]Set as Default Channel[/COLOR]', actions.update_view(remap_url))]
        items.append(item)

    sorted_items = sorted(items, key=lambda item: item['label'])
    return sorted_items



@plugin.route('/stream_remap/<stream_name>/<path>/<icon>/')
def stream_remap(stream_name,path,icon):
    conn = get_conn()
    conn.execute("UPDATE channels SET path=?, icon=? WHERE REPLACE(LOWER(name), ' ', '') LIKE REPLACE(LOWER(?), ' ', '')", [path,icon,stream_name])
    conn.commit()
    if plugin.get_setting("refresh") == 'true':
        xbmc.executebuiltin('Container.Refresh')
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification("TV Listings (xmltv)","Done: Update Shortcut")


def utc2local (utc):
    epoch = time.mktime(utc.timetuple())
    offset = datetime.fromtimestamp (epoch) - datetime.utcfromtimestamp (epoch)
    return utc + offset



def local_time(ttime,year,month,day):
    match = re.search(r'(.{1,2}):(.{2}) {0,1}(.{2})',ttime)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        ampm = match.group(3)
        if ampm == "pm":
            if hour < 12:
                hour = hour + 12
                hour = hour % 24
        else:
            if hour == 12:
                hour = 0

        utc_dt = datetime(int(year),int(month),int(day),hour,minute,0)
        loc_dt = utc2local(utc_dt)
        ttime = "%02d:%02d" % (loc_dt.hour,loc_dt.minute)
    return ttime



def store_channels():
    if plugin.get_setting('ini_type') == '0':
        return

    if plugin.get_setting('ini_reload') == 'true':
        plugin.set_setting('ini_reload','false')
    else:
        return

    conn = get_conn()
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row

    items = []

    if plugin.get_setting('ini_type') == '2':
        url = plugin.get_setting('ini_url')
        r = requests.get(url)
        file_name = 'special://profile/addon_data/plugin.video.tvlistings.xmltv/addons.ini'
        xmltv_f = xbmcvfs.File(file_name,'w')
        xml = r.content
        xmltv_f.write(xml)
        xmltv_f.seek(0,0)
        #NOTE not xmltv_f.close()
        ini_file = file_name
        dt = datetime.now()
        now = int(time.mktime(dt.timetuple()))
        plugin.set_setting("ini_url_last",str(now))
    else:
        ini_file = plugin.get_setting('ini_file')
        path = xbmc.translatePath(plugin.get_setting('ini_file'))
        if not xbmcvfs.exists(path):
            dialog = xbmcgui.Dialog()
            dialog.notification("TV Listings (xmltv)","Error: ini File Not Found!")
            return
        stat = xbmcvfs.Stat(path)
        modified = str(stat.st_mtime())
        plugin.set_setting('ini_last_modified',modified)

    try:
        if plugin.get_setting('ini_type') == '2':
            f = xmltv_f
        else:
            f = xbmcvfs.File(ini_file)
        items = f.read().splitlines()
        f.close()
        addon = 'nothing'

        for item in items:
            if item.startswith('['):
                addon = item.strip('[] \t')
            elif item.startswith('#'):
                pass
            else:
                name_url = item.split('=',1)
                if len(name_url) == 2:
                    name = name_url[0]
                    url = name_url[1]
                    if url:
                        icon = ''
                        conn.execute("INSERT OR IGNORE INTO addons(addon, name, path, icon) VALUES(?, ?, ?, ?, ?)", [addon, name, url, icon])
    except:
        pass
    conn.commit()
    conn.close()
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Load ini File")


def xml2utc(xml):
    match = re.search(r'([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2}) ([+-])([0-9]{2})([0-9]{2})',xml)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        second = int(match.group(6))
        sign = match.group(7)
        hours = int(match.group(8))
        minutes = int(match.group(9))
        dt = datetime(year,month,day,hour,minute,second)
        td = timedelta(hours=hours,minutes=minutes)
        if sign == '+':
            dt = dt - td
        else:
            dt = dt + td
        return dt
    return ''



class FileWrapper(object):
    def __init__(self, filename):
        self.vfsfile = xbmcvfs.File(filename)
        self.size = self.vfsfile.size()
        self.bytesRead = 0

    def close(self):
        self.vfsfile.close()

    def read(self, byteCount):
        self.bytesRead += byteCount
        return self.vfsfile.read(byteCount)

    def tell(self):
        return self.bytesRead



def create_database_tables():
    conn = get_conn()
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS addon_paths(addon TEXT, name TEXT, path TEXT, PRIMARY KEY (path))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS addons(addon TEXT, name TEXT, path TEXT, icon TEXT, PRIMARY KEY (addon, name, path))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS channels(id TEXT, name TEXT, path TEXT, icon TEXT, PRIMARY KEY (id))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS programmes(channel TEXT, title TEXT, sub_title TEXT, start INTEGER, stop INTEGER, date INTEGER, description TEXT, series INTEGER, episode INTEGER, categories TEXT, PRIMARY KEY(channel, start))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS remind(channel TEXT, title TEXT, sub_title TEXT, start INTEGER, stop INTEGER, date INTEGER, description TEXT, series INTEGER, episode INTEGER, categories TEXT, PRIMARY KEY(channel, start))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS watch(channel TEXT, title TEXT, sub_title TEXT, start INTEGER, stop INTEGER, date INTEGER, description TEXT, series INTEGER, episode INTEGER, categories TEXT, PRIMARY KEY(channel, start))')
    conn.commit()
    conn.close()



def xml_channels():
    try:
        updating = plugin.get_setting('xmltv_updating')
    except:
        updating = 'false'
        plugin.set_setting('xmltv_updating', updating)
    if updating == 'true':
        return
    xmltv_type = plugin.get_setting('xmltv_type')
    if plugin.get_setting('xml_reload') == 'true':
        plugin.set_setting('xml_reload','false')
    else:
        try:
            xmltv_type_last = plugin.get_setting('xmltv_type_last')
        except:
            xmltv_type_last = xmltv_type
            plugin.set_setting('xmltv_type_last', xmltv_type)
        if xmltv_type == xmltv_type_last:
            if plugin.get_setting('xmltv_type') == '0': # File
                if plugin.get_setting('xml_reload_modified') == 'true':
                    path = xbmc.translatePath(plugin.get_setting('xmltv_file'))
                    if not xbmcvfs.exists(path):
                        dialog = xbmcgui.Dialog()
                        dialog.notification("TV Listings (xmltv)","Error: xmltv File Not Found!")
                        return
                    stat = xbmcvfs.Stat(path)
                    modified = str(stat.st_mtime())
                    last_modified = plugin.get_setting('xmltv_last_modified')
                    if last_modified == modified:
                        return
                    else:
                        pass
                else:
                    return
            else:
                dt = datetime.now()
                now_seconds = int(time.mktime(dt.timetuple()))
                try:
                    xmltv_url_last = int(plugin.get_setting("xmltv_url_last"))
                except:
                    xmltv_url_last = 0
                if xmltv_url_last + 24*3600 < now_seconds:
                    pass
                else:
                    return
        else:
            drop_channels()
            pass

    xbmc.log("XMLTV UPDATE")
    plugin.set_setting('xmltv_type_last',xmltv_type)

    dialog = xbmcgui.Dialog()

    xbmcvfs.mkdir('special://profile/addon_data/plugin.video.tvlistings.xmltv')

    conn = get_conn()
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    conn.execute('DROP TABLE IF EXISTS programmes')
    create_database_tables()
    c = conn.cursor()
    c.execute('SELECT id FROM channels')
    old_channel_ids = [row["id"] for row in c]

    dialog.notification("TV Listings (xmltv)","downloading xmltv file")
    if plugin.get_setting('xmltv_type') == '1':
        url = plugin.get_setting('xmltv_url')
        r = requests.get(url)
        file_name = 'special://profile/addon_data/plugin.video.tvlistings.xmltv/xmltv.xml'
        xmltv_f = xbmcvfs.File(file_name,'w')
        xml = r.content
        if r.status_code == 404:
            dialog.notification("TV Listings (xmltv)","ERROR: No xmltv Url Data")
            return
        xmltv_f.write(xml)
        xmltv_f.close()
        xmltv_file = file_name
        dt = datetime.now()
        now = int(time.mktime(dt.timetuple()))
        plugin.set_setting("xmltv_url_last",str(now))
    else:
        xmltv_file = plugin.get_setting('xmltv_file')
        path = xbmc.translatePath(plugin.get_setting('xmltv_file'))
        if not xbmcvfs.exists(path):
            dialog = xbmcgui.Dialog()
            dialog.notification("TV Listings (xmltv)","Error: xmltv File Not Found!")
            return
        stat = xbmcvfs.Stat(path)
        modified = str(stat.st_mtime())
        plugin.set_setting('xmltv_last_modified',modified)

    dialog.notification("TV Listings (xmltv)","finished downloading xmltv file")

    xml_f = FileWrapper(xmltv_file)
    if xml_f.size == 0:
        return
    context = ET.iterparse(xml_f, events=("start", "end"))
    context = iter(context)
    event, root = context.next()
    last = datetime.now()
    new_channel_ids = []
    for event, elem in context:
        if event == "end":
            now = datetime.now()
            if elem.tag == "channel":
                id = elem.attrib['id']
                new_channel_ids.append(id)
                display_name = elem.find('display-name').text
                try:
                    icon = elem.find('icon').attrib['src']
                except:
                    icon = ''
                    if plugin.get_setting('logo_type') == 0:
                        path = plugin.get_setting('logo_folder')
                        if path:
                            icon = os.path.join(path,display_name,".png")
                    else:
                        path = plugin.get_setting('logo_url')
                        if path:
                            icon = "%s/%s.png" % (path,display_name)

                conn.execute("INSERT OR IGNORE INTO channels(id, name, path, icon) VALUES(?, ?, ?, ?)", [id, display_name, '', icon])
                if (now - last).seconds > 0.5:
                    dialog.notification("TV Listings (xmltv)","loading channels: "+display_name)
                    last = now

            elif elem.tag == "programme":
                programme = elem
                start = programme.attrib['start']
                start = xml2utc(start)
                start = utc2local(start)
                stop = programme.attrib['stop']
                stop = xml2utc(stop)
                stop = utc2local(stop)
                channel = programme.attrib['channel']
                title = programme.find('title').text
                match = re.search(r'(.*?)"}.*?\(\?\)$',title) #BUG in webgrab
                if match:
                    title = match.group(1)
                try:
                    sub_title = programme.find('sub-title').text
                except:
                    sub_title = ''
                try:
                    date = programme.find('date').text
                except:
                    date = ''
                try:
                    description = programme.find('desc').text
                except:
                    description = ''
                try:
                    episode_num = programme.find('episode-num').text
                except:
                    episode_num = ''
                series = 0
                episode = 0
                match = re.search(r'(.*?)\.(.*?)[\./]',episode_num)
                if match:
                    try:
                        series = int(match.group(1)) + 1
                        episode = int(match.group(2)) + 1
                    except:
                        pass
                series = str(series)
                episode = str(episode)
                categories = ''
                for category in programme.findall('category'):
                    categories = ','.join((categories,category.text)).strip(',')

                total_seconds = time.mktime(start.timetuple())
                start = int(total_seconds)
                total_seconds = time.mktime(stop.timetuple())
                stop = int(total_seconds)
                conn.execute("INSERT OR IGNORE INTO programmes(channel ,title , sub_title , start , stop, date, description , series , episode , categories) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [channel ,title , sub_title , start , stop, date, description , series , episode , categories])
                if (now - last).seconds > 0.5:
                    dialog.notification("TV Listings (xmltv)","loading programmes: "+channel)
                    last = now
            root.clear()

    remove_channel_ids = set(old_channel_ids) - set(new_channel_ids)
    for id in remove_channel_ids:
        conn.execute('DELETE FROM channels WHERE id=?', [id])
    conn.commit()
    conn.close()
    plugin.set_setting('xmltv_updating', 'false')
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Load xmltv File")



@plugin.route('/channels')
def channels():
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()

    if plugin.get_setting('hide_unmapped') == 'false':
        c.execute('SELECT * FROM channels')
    else:
        c.execute('SELECT * FROM channels WHERE path IS NOT ""')
    items = []
    for row in c:
        channel_id = row['id']
        channel_name = row['name']
        img_url = row['icon']
        label = "[COLOR gold][B]%s[/B][/COLOR]" % (channel_name)
        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['path'] = plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))
        items.append(item)
    c.close()

    sorted_items = sorted(items, key=lambda item: item['label'])
    return sorted_items



@plugin.route('/now_next_time/<seconds>/<when>')
def now_next_time(seconds,when):
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()

    if plugin.get_setting('hide_unmapped') == 'false':
        c.execute('SELECT * FROM channels')
    else:
        c.execute('SELECT * FROM channels WHERE path IS NOT ""')
    channels = [(row['id'], row['name'], row['icon'], row["path"]) for row in c]

    now = datetime.fromtimestamp(float(seconds))
    total_seconds = time.mktime(now.timetuple())

    items = []
    for (channel_id, channel_name, img_url, path) in channels:
        c.execute('SELECT * FROM remind WHERE channel=? ORDER BY start', [channel_id])
        remind = [row['start'] for row in c]
        c.execute('SELECT * FROM watch WHERE channel=? ORDER BY start', [channel_id])
        watch = [row['start'] for row in c]
        c.execute('SELECT start FROM programmes WHERE channel=? ORDER BY start', [channel_id])
        programmes = [row['start'] for row in c]

        times = sorted(programmes)
        max = len(times)
        less = [i for i in times if i <= total_seconds]
        index = len(less) - 1
        if index < 0:
            continue
        now_start = times[index]

        c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id,now_start])
        now = datetime.fromtimestamp(now_start)
        now = "%02d:%02d" % (now.hour,now.minute)
        row = c.fetchone()
        now_title = row['title']
        now_stop = row['stop']
        if now_stop < total_seconds:
            now_title = "[I]%s[/I]" % now_title
        else:
            now_title = "[B]%s[/B]" % now_title

        if now_start in watch:
            now_title_format = "[COLOR cornflowerblue]%s[/COLOR]" % now_title
        elif now_start in remind:
            now_title_format = "[COLOR crimson]%s[/COLOR]" % now_title
        else:
            now_title_format = "[COLOR orange]%s[/COLOR]" % now_title

        next = ''
        next_title = ''
        next_start = ''
        if index+1 < max:
            next_start = times[index + 1]
            c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id,next_start])
            next = datetime.fromtimestamp(next_start)
            next = "%02d:%02d" % (next.hour,next.minute)
            next_title = c.fetchone()['title']

        if next_start in watch:
            next_title_format = "[COLOR cornflowerblue][B]%s[/B][/COLOR]" % next_title
        elif next_start in remind:
            next_title_format = "[COLOR crimson][B]%s[/B][/COLOR]" % next_title
        else:
            next_title_format = "[COLOR white][B]%s[/B][/COLOR]" % next_title

        after = ''
        after_title = ''
        after_start = ''
        if (index+2) < max:
            after_start = times[index + 2]
            c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id,after_start])
            after = datetime.fromtimestamp(after_start)
            after = "%02d:%02d" % (after.hour,after.minute)
            after_title = c.fetchone()['title']

        if after_start in watch:
            after_title_format = "[COLOR cornflowerblue][B]%s[/B][/COLOR]" % after_title
        elif after_start in remind:
            after_title_format = "[COLOR crimson][B]%s[/B][/COLOR]" % after_title
        else:
            after_title_format = "[COLOR grey][B]%s[/B][/COLOR]" % after_title

        if when == "now":
            if  plugin.get_setting('show_channel_name') == 'true':
                label = "[COLOR gold][B]%s[/B][/COLOR] %s %s %s %s %s %s" % \
                (channel_name,now,now_title_format,next,next_title_format,after,after_title_format)
            else:
                label = "%s %s %s %s %s %s" % \
                (now,now_title_format,next,next_title_format,after,after_title_format)
        else:
            if  plugin.get_setting('show_channel_name') == 'true':
                label = "[COLOR gold][B]%s[/B][/COLOR] %s %s %s %s" % \
                (channel_name,next,next_title_format,after,after_title_format)
            else:
                label = "%s %s %s %s" % \
                (next,next_title_format,after,after_title_format)

        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['path'] = plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))
        context_items = []
        if path:
            play_url = plugin.url_for('play_media', path=path)
            context_items.append(('[COLOR gold]Play Channel[/COLOR]', actions.update_view(play_url)))
        choose_url = plugin.url_for('channel_remap_all', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), channel_play=True)
        search_url = plugin.url_for(search_addons,channel_name=channel_name.encode("utf8"))
        context_items.append(('[COLOR seagreen]Search Channel[/COLOR]', actions.update_view(search_url)))
        context_items.append(('[COLOR crimson]Default Shortcut[/COLOR]', actions.update_view(choose_url)))
        item['context_menu'] = context_items
        items.append(item)

    if plugin.get_setting('sort_now') == 'true':
        sorted_items = sorted(items, key=lambda item: item['label'])
        return sorted_items
    else:
        return items


@plugin.route('/hourly')
def hourly():
    global big_list_view
    big_list_view = True
    items = []

    dt = datetime.now()
    dt = dt.replace(hour=0, minute=0, second=0)

    for day in ("Today","Tomorrow"):
        label = "[COLOR crimson][B]%s[/B][/COLOR]" % (day)
        items.append({'label':label,'path':plugin.url_for('hourly'),'thumbnail':get_icon_path('calendar')})
        for hour in range(0,24):
            label = "[COLOR cornflowerblue][B]%02d:00[/B][/COLOR]" % (hour)
            total_seconds = str(time.mktime(dt.timetuple()))
            items.append({'label':label,'path':plugin.url_for('now_next_time',seconds=total_seconds, when='now'),'thumbnail':get_icon_path('clock')})
            dt = dt + timedelta(hours=1)

    return items


@plugin.route('/prime')
def prime():
    prime = plugin.get_setting('prime')
    dt = datetime.now()
    dt = dt.replace(hour=int(prime), minute=0, second=0)
    total_seconds = str(time.mktime(dt.timetuple()))
    items = now_next_time(total_seconds,'now')
    return items


@plugin.route('/now_next/<when>')
def now_next(when):
    dt = datetime.now()
    total_seconds = str(time.mktime(dt.timetuple()))
    items = now_next_time(total_seconds,when)
    return items


@plugin.route('/listing/<channel_id>/<channel_name>')
def listing(channel_id,channel_name):
    global big_list_view
    big_list_view = True

    calendar_icon = get_icon_path('calendar')

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT *, name FROM channels')
    channels = dict((row['id'], (row['name'], row['icon'], row["path"])) for row in c)
    c.execute('SELECT * FROM remind WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    remind = [row['start'] for row in c]
    c.execute('SELECT * FROM watch WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    watch = [row['start'] for row in c]
    c.execute('SELECT * FROM programmes WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    items = channel(channel_id,channel_name)
    last_day = ''
    for row in c:
        channel_id = row['channel']
        (channel_name, img_url, path) = channels[channel_id]
        title = row['title']
        sub_title = row['sub_title']
        start = row['start']
        stop = row['stop']
        date = row['date']
        plot = row['description']
        season = row['series']
        episode = row['episode']
        categories = row['categories']

        now = datetime.now()
        dt = datetime.fromtimestamp(start)
        dt_stop = datetime.fromtimestamp(stop)
        mode = 'future'
        if dt < now:
            mode = 'past'
            if dt_stop > now:
                mode = 'present'

        day = dt.day
        if day != last_day:
            last_day = day
            label = "[COLOR white][B]%s[/B][/COLOR]" % (dt.strftime("%A %d/%m/%y"))
            items.append({'label':label,
            'is_playable':True,
            'thumbnail': calendar_icon,
            'path':plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))})

        if not season:
            season = '0'
        if not episode:
            episode = '0'
        if date:
            title = "%s (%s)" % (title,date)
        if sub_title:
            plot = "[B]%s[/B]: %s" % (sub_title,plot)
        if mode == "present":
            ttime = "[COLOR white][B]%02d:%02d[/B][/COLOR]" % (dt.hour,dt.minute)
        else:
            ttime = "%02d:%02d" % (dt.hour,dt.minute)

        if start in watch:
            title_format = "[COLOR cornflowerblue][B]%s[/B][/COLOR]" % title
        elif start in remind:
            title_format = "[COLOR crimson][B]%s[/B][/COLOR]" % title
        else:
            if mode == 'past':
                title_format = "[COLOR grey][B]%s[/B][/COLOR]" % title
            else:
                title_format = "[COLOR orange][B]%s[/B][/COLOR]" % title

        if mode == 'past':
            channel_format = "[COLOR grey]%s[/COLOR]" % channel_name
        else:
            channel_format = "[COLOR gold][B]%s[/B][/COLOR]" % channel_name

        if  plugin.get_setting('show_channel_name') == 'true':
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s %s" % (channel_format,ttime,title_format,plot)
            else:
                label = "%s %s %s" % (channel_format,ttime,title_format)
        else:
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s" % (ttime,title_format,plot)
            else:
                label = "%s %s" % (ttime,title_format)

        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['info'] = {'plot':plot, 'season':int(season), 'episode':int(episode), 'genre':categories}
        item['path'] = plugin.url_for('play', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), title=title.encode("utf8"), season=season, episode=episode, start=start, stop=stop)
        context_items = []
        if path:
            play_url = plugin.url_for('play_media', path=path)
            context_items.append(('[COLOR gold]Play Channel[/COLOR]', actions.update_view(play_url)))
        choose_url = plugin.url_for('channel_remap_all', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), channel_play=True)
        search_url = plugin.url_for(search_addons,channel_name=channel_name.encode("utf8"))
        context_items.append(('[COLOR seagreen]Search Channel[/COLOR]', actions.update_view(search_url)))
        context_items.append(('[COLOR crimson]Default Shortcut[/COLOR]', actions.update_view(choose_url)))
        item['context_menu'] = context_items
        items.append(item)
    c.close()

    return items


@plugin.route('/search/<programme_name>')
def search(programme_name):
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT *, name FROM channels')
    channels = dict((row['id'], (row['name'], row['icon'], row['path'])) for row in c)
    calendar_icon = get_icon_path('calendar')
    c.execute('SELECT * FROM remind ORDER BY channel, start')
    remind = {}
    for row in c:
        if not row['channel'] in remind:
            remind[row['channel']] = []
        remind[row['channel']].append(row['start'])
    c.execute('SELECT * FROM watch ORDER BY channel, start')
    watch = {}
    for row in c:
        if not row['channel'] in watch:
            watch[row['channel']] = []
        watch[row['channel']].append(row['start'])

    c.execute("SELECT * FROM programmes WHERE LOWER(title) LIKE LOWER(?) ORDER BY start, channel", ['%'+programme_name.decode("utf8")+'%'])
    last_day = ''
    items = []
    for row in c:
        channel_id = row['channel']
        (channel_name, img_url, path) = channels[channel_id]
        title = row['title']
        sub_title = row['sub_title']
        start = row['start']
        stop = row['stop']
        date = row['date']
        plot = row['description']
        season = row['series']
        episode = row['episode']
        categories = row['categories']

        now = datetime.now()
        dt = datetime.fromtimestamp(start)
        dt_stop = datetime.fromtimestamp(stop)
        mode = 'future'
        if dt < now:
            mode = 'past'
            if dt_stop > now:
                mode = 'present'

        day = dt.day
        if day != last_day:
            last_day = day
            label = "[COLOR white][B]%s[/B][/COLOR]" % (dt.strftime("%A %d/%m/%y"))
            items.append({'label':label,
            'is_playable':True,
            'thumbnail': calendar_icon,
            'path':plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))})

        if not season:
            season = '0'
        if not episode:
            episode = '0'
        if date:
            title = "%s (%s)" % (title,date)
        if sub_title:
            plot = "[B]%s[/B]: %s" % (sub_title,plot)
        if mode == "present":
            ttime = "[COLOR white][B]%02d:%02d[/B][/COLOR]" % (dt.hour,dt.minute)
        else:
            ttime = "%02d:%02d" % (dt.hour,dt.minute)

        if mode == 'past':
            title_format = "[COLOR grey][B]%s[/B][/COLOR]" % title
        else:
            title_format = "[COLOR orange][B]%s[/B][/COLOR]" % title
        if channel_id in remind:
            if start in remind[channel_id]:
                title_format = "[COLOR crimson][B]%s[/B][/COLOR]" % title
        if channel_id in watch:
            if start in watch[channel_id]:
                title_format = "[COLOR cornflowerblue][B]%s[/B][/COLOR]" % title

        if mode == 'past':
            channel_format = "[COLOR grey]%s[/COLOR]" % channel_name
        else:
            channel_format = "[COLOR gold][B]%s[/B][/COLOR]" % channel_name

        if  plugin.get_setting('show_channel_name') == 'true':
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s %s" % (channel_format,ttime,title_format,plot)
            else:
                label = "%s %s %s" % (channel_format,ttime,title_format)
        else:
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s" % (ttime,title_format,plot)
            else:
                label = "%s %s" % (ttime,title_format)


        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['info'] = {'plot':plot, 'season':int(season), 'episode':int(episode), 'genre':categories}
        item['path'] = plugin.url_for('play', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), title=title.encode("utf8"), season=season, episode=episode, start=start, stop=stop)
        context_items = []
        if path:
            play_url = plugin.url_for('play_media', path=path)
            context_items.append(('[COLOR gold]Play Channel[/COLOR]', actions.update_view(play_url)))
        choose_url = plugin.url_for('channel_remap_all', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), channel_play=True)
        search_url = plugin.url_for(search_addons,channel_name=channel_name.encode("utf8"))
        context_items.append(('[COLOR seagreen]Search Channel[/COLOR]', actions.update_view(search_url)))
        context_items.append(('[COLOR crimson]Default Shortcut[/COLOR]', actions.update_view(choose_url)))
        item['context_menu'] = context_items
        items.append(item)
    c.close()
    return items


@plugin.route('/reminders')
def reminders():
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT *, name FROM channels')
    channels = dict((row['id'], (row['name'], row['icon'])) for row in c)
    calendar_icon = get_icon_path('calendar')
    c.execute('SELECT * FROM remind ORDER BY channel, start')
    remind = {}
    for row in c:
        if not row['channel'] in remind:
            remind[row['channel']] = []
        remind[row['channel']].append(row['start'])
    c.execute('SELECT * FROM watch ORDER BY channel, start')
    watch = {}
    for row in c:
        if not row['channel'] in watch:
            watch[row['channel']] = []
        watch[row['channel']].append(row['start'])

    c.execute('SELECT * FROM remind UNION SELECT * FROM watch ORDER BY start, channel')
    last_day = ''
    items = []
    for row in c:
        channel_id = row['channel']
        if channel_id not in channels:
            continue
        (channel_name, img_url) = channels[channel_id]
        title = row['title']
        sub_title = row['sub_title']
        start = row['start']
        stop = row['stop']
        date = row['date']
        plot = row['description']
        season = row['series']
        episode = row['episode']
        categories = row['categories']

        now = datetime.now()
        dt = datetime.fromtimestamp(start)
        dt_stop = datetime.fromtimestamp(stop)
        mode = 'future'
        if dt < now:
            mode = 'past'
            if dt_stop > now:
                mode = 'present'

        day = dt.day
        if day != last_day:
            last_day = day
            label = "[COLOR white][B]%s[/B][/COLOR]" % (dt.strftime("%A %d/%m/%y"))
            items.append({'label':label,
            'is_playable':True,
            'thumbnail': calendar_icon,
            'path':plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))})

        if not season:
            season = '0'
        if not episode:
            episode = '0'
        if date:
            title = "%s (%s)" % (title,date)
        if sub_title:
            plot = "[B]%s[/B]: %s" % (sub_title,plot)
        if mode == "present":
            ttime = "[COLOR white][B]%02d:%02d[/B][/COLOR]" % (dt.hour,dt.minute)
        else:
            ttime = "%02d:%02d" % (dt.hour,dt.minute)

        if mode == 'past':
            title_format = "[COLOR grey][B]%s[/B][/COLOR]" % title
        else:
            title_format = "[COLOR orange][B]%s[/B][/COLOR]" % title
        if channel_id in remind:
            if start in remind[channel_id]:
                if mode == 'past':
                    title_format = "[COLOR crimson]%s[/COLOR]" % title
                else:
                    title_format = "[COLOR crimson][B]%s[/B][/COLOR]" % title
        if channel_id in watch:
            if start in watch[channel_id]:
                if mode == 'past':
                    title_format = "[COLOR cornflowerblue]%s[/COLOR]" % title
                else:
                    title_format = "[COLOR cornflowerblue][B]%s[/B][/COLOR]" % title

        if mode == 'past':
            channel_format = "[COLOR grey]%s[/COLOR]" % channel_name
        else:
            channel_format = "[COLOR gold][B]%s[/B][/COLOR]" % channel_name

        if  plugin.get_setting('show_channel_name') == 'true':
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s %s" % (channel_format,ttime,title_format,plot)
            else:
                label = "%s %s %s" % (channel_format,ttime,title_format)
        else:
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s" % (ttime,title_format,plot)
            else:
                label = "%s %s" % (ttime,title_format)

        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['info'] = {'plot':plot, 'season':int(season), 'episode':int(episode), 'genre':categories}
        item['path'] = plugin.url_for('play', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), title=title.encode("utf8"), season=season, episode=episode, start=start, stop=stop)
        items.append(item)
    c.close()
    return items


@plugin.route('/search_dialog')
def search_dialog():
    dialog = xbmcgui.Dialog()
    name = dialog.input('Search for programme', type=xbmcgui.INPUT_ALPHANUM)
    if name:
        return search(name)


@plugin.route('/nuke')
def nuke():
    TARGETFOLDER = xbmc.translatePath(
        'special://profile/addon_data/plugin.video.tvlistings.xmltv'
        )
    dialog = xbmcgui.Dialog()
    ok = dialog.ok('TV Listings (xmltv)', '[COLOR crimson][B]Delete Everything in addon_data Folder?![/B][/COLOR]')
    if not ok:
        return
    if os.path.exists( TARGETFOLDER ):
            shutil.rmtree( TARGETFOLDER , ignore_errors=True)

    dialog.notification("TV Listings (xmltv)","Done: Everything Deleted!")

def urlencode_path(path):
    from urlparse import urlparse, parse_qs, urlunparse
    path = path.encode("utf8")
    o = urlparse(path)
    query = parse_qs(o.query)
    path = urlunparse([o.scheme, o.netloc, o.path, o.params, urllib.urlencode(query, True), o.fragment])
    return path


def get_addon_info(id):
    try:
        addon = xbmcaddon.Addon(id)
        name = remove_formatting(addon.getAddonInfo('name'))
        name = remove_formatting(name)
        icon = addon.getAddonInfo('icon')
        return (name,icon)
    except:
        return ('','')


@plugin.route('/browse_addon_paths')
def browse_addon_paths():
    global big_list_view
    big_list_view = True

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM addon_paths")
    cc = conn.cursor()
    cc.execute("SELECT path,name FROM addon_paths")
    paths = [row["path"] for row in cc]

    items = []
    for row in c:
        addon_id = row["addon"]
        addon_path = row["path"]
        path_name = row["name"]

        (addon_name,addon_icon) = get_addon_info(addon_id)
        if addon_name:

            label = "[COLOR seagreen][B]%s[/B][/COLOR] [COLOR gold][B]%s[/B][/COLOR]" % (addon_name,path_name)
            if addon_path not in paths:
                folder_url = plugin.url_for('add_addon_channels', addon=addon_id, path=addon_path, path_name=name.encode("utf8"))
                folder_label = '[COLOR crimson][B]Add Folder[/B][/COLOR]'
            else:
                folder_url = plugin.url_for('remove_addon_path', path=addon_path)
                folder_label = '[COLOR gold][B]Remove Folder[/B][/COLOR]'

            item = {'label':label,
            'path':plugin.url_for('browse_path', addon=addon_id, name=path_name.encode("utf8"), path=addon_path),
            'thumbnail':addon_icon}
            item['context_menu'] = [(folder_label, actions.update_view(folder_url))]
            items.append(item)

    sorted_items = sorted(items, key=lambda item: remove_formatting(item['label']).lower())
    return sorted_items


@plugin.route('/browse_addons')
def browse_addons():
    global big_list_view
    big_list_view = True
    try:
        response = RPC.addons.get_addons(type="xbmc.addon.video",properties=["thumbnail"])
    except:
         return
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT addon,path FROM addon_paths")
    addon_paths = [row["addon"] for row in c]
    cc = conn.cursor()
    cc.execute("SELECT path,name FROM addon_paths")
    paths = [row["path"] for row in cc]

    addons = response["addons"]
    addon_ids = [a["addonid"] for a in addons]
    items = []
    for addon_id in addon_ids:
        path = "plugin://%s" % addon_id
        path = urlencode_path(path)
        (name,icon) = get_addon_info(addon_id)
        if name:
            if addon_id in addon_paths:
                label = "[COLOR gold][B]%s[/B][/COLOR]" % name
            else:
                label = "[COLOR grey][B]%s[/B][/COLOR]" % name
            item = {'label':label,
            'path':plugin.url_for('browse_path', addon=addon_id, name=name, path=path),
            'thumbnail':icon}
            if path not in paths:
                url = plugin.url_for('add_addon_channels', addon=addon_id, path=path, path_name=name.encode("utf8"))
                label = '[COLOR crimson][B]Add Folder[/B][/COLOR]'
            else:
                url = plugin.url_for('remove_addon_path', path=path)
                label = '[COLOR gold][B]Remove Folder[/B][/COLOR]'
            item['context_menu'] = [(label, actions.update_view(url))]
            items.append(item)

    sorted_items = sorted(items, key=lambda item: remove_formatting(item['label']).lower())
    return sorted_items


@plugin.route('/remove_addon_path/<path>')
def remove_addon_path(path):
    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM addon_paths WHERE path=?', [path])
    conn.commit()
    conn.close()
    if plugin.get_setting("refresh") == 'true':
        xbmc.executebuiltin('Container.Refresh')
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification("TV Listings (xmltv)","Done: Removed")


@plugin.route('/browse_path/<addon>/<name>/<path>')
def browse_path(addon,name,path):
    global big_list_view
    big_list_view = True

    addon_icon = xbmcaddon.Addon(addon).getAddonInfo('icon')

    try:
        response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
    except:
         return

    files = response["files"]

    dirs = dict([[f["label"], f["file"]] for f in files if f["filetype"] == "directory"])
    links = dict([[f["file"], f["label"]] for f in files if f["filetype"] == "file"])
    thumbnails = dict([[f["file"], f["thumbnail"]] for f in files])

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT path,name FROM addon_paths")
    paths = [row["path"] for row in c]

    top_items = []

    c.execute("SELECT * FROM addon_paths WHERE path=?", [path])
    row = c.fetchone()
    if row is None:
        default_menu = True
        remove_menu = False
    else:
        default_menu = False
        remove_menu = True

    if default_menu:
        item = {'label':'[COLOR crimson][B]Add Folder[/B][/COLOR]',
        'path':plugin.url_for('add_addon_channels', addon=addon, path=path, path_name=name),
        'thumbnail':addon_icon,
        'is_playable':False}
        top_items.append(item)

    if remove_menu:
        item = {'label':'[COLOR gold][B]Remove Folder[/B][/COLOR]',
        'path':plugin.url_for('remove_addon_path', path=path),
        'thumbnail':addon_icon,
        'is_playable':False}
        top_items.append(item)

    items = []

    for dir in sorted(dirs):
        path = dirs[dir]
        dir = remove_formatting(dir)
        if path in paths:
            label = "[COLOR gold][B]%s[/B][/COLOR]" % dir
        else:
            label = "[COLOR grey][B]%s[/B][/COLOR]" % dir
        item = {'label':label,
        'path':plugin.url_for('browse_path', addon=addon, name=dir.encode("utf8"), path=path),
        'thumbnail':addon_icon,
        'is_playable':False}
        if path not in paths:
            url = plugin.url_for('add_addon_channels', addon=addon, path=path, path_name=dir.encode("utf8"))
            label = '[COLOR crimson][B]Add Folder[/B][/COLOR]'
        else:
            url = plugin.url_for('remove_addon_path', path=path)
            label = '[COLOR gold][B]Remove Folder[/B][/COLOR]'
        item['context_menu'] = [(label, actions.update_view(url))]
        items.append(item)
    for path in sorted(links):
        label = links[path]
        label = remove_formatting(label)
        icon = thumbnails[path]
        item = {'label':label.encode("utf8"),
        'path':plugin.url_for('play_media',path=path),
        'is_playable':False,
        'thumbnail':icon}
        items.append(item)

    sorted_items = sorted(items, key=lambda item: remove_formatting(item['label']))
    items = top_items + sorted_items
    return items


@plugin.route('/reload_addon_paths')
def reload_addon_paths():
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM addon_paths')
    addon_paths = [(row["addon"],row["path"],row["name"]) for row in c]
    for addon_path in addon_paths:
        add_addon_channels(addon_path[0],addon_path[1],addon_path[2])
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Addon Paths Refreshed")



@plugin.route('/add_addon_channels/<addon>/<path>/<path_name>/')
def add_addon_channels(addon,path,path_name):
    try:
        response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
    except:
         return

    files = response["files"]
    labels = dict([[f["file"], f["label"]] for f in files if f["filetype"] == "file"])
    thumbnails = dict([[f["file"], f["thumbnail"]] for f in files])

    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO addon_paths(addon, name, path) VALUES(?, ?, ?)", [addon, path_name.decode("utf8"), path])

    for file in sorted(labels):
        label = labels[file]
        label = re.sub('\[.*?\]','',label)
        icon = thumbnails[file].strip("/")

        log(icon)
        conn.execute("INSERT OR REPLACE INTO addons(addon, name, path, icon) VALUES(?, ?, ?, ?)", [addon, label, file, icon])

    conn.commit()
    conn.close()
    if plugin.get_setting("refresh") == 'true':
        xbmc.executebuiltin('Container.Refresh')
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification("TV Listings (xmltv)","Done: Added")


@plugin.route('/add_defaults/<addon>/<path>/<addon_name>')
def add_defaults(addon,path,addon_name):
    try:
        response = RPC.files.get_directory(media="video", directory=path, properties=["thumbnail"])
    except:
         return
    links = dict([[f["label"], f["file"]] for f in files if f["filetype"] == "file"])
    addon = remove_formatting(xbmcaddon.Addon(addon))
    name = addon.getAddonInfo('name')

    for link in sorted(links):
        if addon_name == "True":
            title = "%s [COLOR seagreen]%s[/COLOR]" % (link,name)
        else:
            title = link




@plugin.route('/')
def index():
    items = [
    {
        'label': '[COLOR orange][B]Now[/B][/COLOR]',
        'path': plugin.url_for('now_next', when='now'),
        'thumbnail':get_icon_path('clock'),
    },
    {
        'label': '[COLOR white][B]Next[/B][/COLOR]',
        'path': plugin.url_for('now_next', when='next'),
        'thumbnail':get_icon_path('clock'),
    },
    {
        'label': '[COLOR cornflowerblue][B]Hourly[/B][/COLOR]',
        'path': plugin.url_for('hourly'),
        'thumbnail':get_icon_path('clock'),
    },
    {
        'label': '[COLOR orange][B]Prime Time[/B][/COLOR]',
        'path': plugin.url_for('prime'),
        'thumbnail':get_icon_path('favourites'),
    },
    {
        'label': '[COLOR crimson][B]Channel Listings[/B][/COLOR]',
        'path': plugin.url_for('channels'),
        'thumbnail':get_icon_path('tv'),
    },
    {
        'label': '[COLOR gold][B]Search Programmes[/B][/COLOR]',
        'path': plugin.url_for('search_dialog'),
        'thumbnail':get_icon_path('search'),
    },
    {
        'label': '[COLOR cornflowerblue][B]Reminders[/B][/COLOR]',
        'path': plugin.url_for('reminders'),
        'thumbnail':get_icon_path('clock'),
    },
    {
        'label': '[COLOR gold][B]Channel Player[/B][/COLOR]',
        'path': plugin.url_for('channel_list'),
        'thumbnail':get_icon_path('tv'),
    },
    {
        'label': '[COLOR crimson][B]Default Shortcuts[/B][/COLOR]',
        'path': plugin.url_for('channel_remap'),
        'thumbnail':get_icon_path('magnet'),
    },
    {
        'label': '[COLOR seagreen][B]Addon Shortcuts[/B][/COLOR]',
        'path': plugin.url_for('addon_streams'),
        'thumbnail':get_icon_path('settings'),
    },
    {
        'label': '[COLOR gold][B]Addon Folders[/B][/COLOR]',
        'path': plugin.url_for('browse_addon_paths'),
        'thumbnail':get_icon_path('settings'),
    },
    {
        'label': '[COLOR grey][B]Addon Browser[/B][/COLOR]',
        'path': plugin.url_for('browse_addons'),
        'thumbnail':get_icon_path('settings'),
    },
    ]
    return items


if __name__ == '__main__':
    create_database_tables()
    xml_channels()
    store_channels()
    plugin.run()
    if big_list_view == True:
        view_mode = int(plugin.get_setting('view_mode'))
        plugin.set_view_mode(view_mode)