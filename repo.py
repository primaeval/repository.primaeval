import subprocess
import re
import os
import shutil
import zipfile
import time
import md5
import sys

# USAGE: python -u repo.py <clean>

repos = {
    'jarvis': {
        'master': [
            "context.simple.favourites",
            "plugin.audio.bbc",
            "plugin.audio.favourites",
            "plugin.program.downloader",
            "plugin.program.fixtures",
            "plugin.program.simple.favourites",
            "plugin.video.addons.ini.creator",
            "plugin.video.addons.ini.player",
            "plugin.video.bbc",
            "plugin.video.bbc.live",
            "plugin.video.boilerroom",
            "plugin.video.favourites",
            "plugin.video.hls.playlist.player",
            "plugin.video.playlist.player",
            "plugin.video.pvr.plugin.player",
            "plugin.video.rageagain.again",
            "plugin.video.replay",
            "plugin.video.search.and.play",
            "plugin.video.stream.searcher",
            "plugin.video.tvlistings",
            "plugin.video.tvlistings.xmltv",
            "plugin.video.tvlistings.yo",
            "script.games.play.mame",
            "script.skin.tightener",
            "script.tvguide.fullscreen",
            "script.tvguide.fullscreen.skin.carnelian",
            "script.tvguide.fullscreen.skin.lapis",
            "script.tvguide.fullscreen.skin.onyx",
            "script.tvguide.fullscreen.skin.wmc",
            "script.webgrab",
            "skin.confluence.wall",
            "skin.naked",
            "plugin.video.iptv.recorder",
            "plugin.program.xmltv.meld",
            "plugin.video.imdb.search",
            "plugin.video.imdb.watchlists",
            "repository.primaeval",
            "repository.imdbsearch",
        ],
        'jarvis': {
            "script.tvguide.fullscreen.skin.tycoo",
            "script.tvguide.fullscreen.skin.kjb85",
        }
    },
    'krypton': {
        'master': [
            "script.tvguide.fullscreen.skin.tycoo",
            "script.tvguide.fullscreen.skin.kjb85",
            "skin.estuary.wall",
            ],
        'krypton': [
            "script.tvguide.fullscreen",
            "script.tvguide.fullscreen.skin.carnelian",
            "script.tvguide.fullscreen.skin.lapis",
            "script.tvguide.fullscreen.skin.onyx",
            "script.tvguide.fullscreen.skin.wmc",
            "skin.confluence.wall",
            ]
    }
}

class color:
    pink = '\033[95m'
    blue = '\033[94m'
    green = '\033[92m'
    orange = '\033[93m'
    red = '\033[91m'
    end = '\033[0m'
    bold = '\033[1m'
    underline = '\033[4m'

subprocess.call(["rm",'.gitignore'])

root = '.'

all_addons = set()

for repo in ['jarvis', 'krypton']:

    print color.bold + color.green + "### REPO: " + repo + " ###" + color.end

    repo_root = repo

    if os.path.exists(repo_root):
        shutil.rmtree(repo_root,ignore_errors=True, onerror=None)
    time.sleep(5)

    branches = repos.get(repo,[])

    zips = repo_root
    try:os.makedirs(zips)
    except:exit()

    addon_xml = os.path.join(repo_root,'addons.xml')
    x = open(addon_xml,'w')
    x.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
    x.write('<addons>\n\n')

    for branch in ['master', 'jarvis', 'krypton']:

        print color.blue + "### REPO: " + repo + '>>> "BRANCH:"' + branch + ' >>>'+ color.end

        addons = branches.get(branch,[])

        for addon in addons:

            print color.pink  +  addon+ color.end

            all_addons.add(addon)

            try: os.makedirs(os.path.join(zips,addon))
            except: exit()

            if sys.argv[1] == "clean":
                subprocess.call(["rm",'-rf',addon])

            if addon not in  ["repository.primaeval", "repository.imdbsearch" ]:
                git_repo = 'https://github.com/primaeval/'+addon+'.git'

                if not os.path.isdir(addon):
                    subprocess.call(["git","clone",git_repo,'-b',branch])
                    tag =subprocess.check_output(["git","describe","--abbrev=0", "--tags"],cwd=addon)

                else:
                    subprocess.call(["git","checkout",branch],cwd=addon)
                    subprocess.call(["git","pull"],cwd=addon)
                    tag =subprocess.check_output(["git","describe","--abbrev=0", "--tags"],cwd=addon)

                tag = tag.strip()
                subprocess.call(["git","checkout","-b","temp", "tags/"+tag],cwd=addon)

            try:shutil.copyfile(os.path.join(addon,'addon.xml'),os.path.join(zips, addon, 'addon.xml'))
            except:pass
            try:shutil.copyfile(os.path.join(addon,'changelog.txt'),os.path.join(zips, addon, 'changelog.txt'))
            except:pass
            try:shutil.copyfile(os.path.join(addon,'icon.png'),os.path.join(zips, addon, 'icon.png'))
            except:pass
            try:shutil.copyfile(os.path.join(addon,'fanart.jpg'),os.path.join(zips, addon, 'fanart.jpg'))
            except:pass
            if repo != "jarvis":
                try:os.makedirs(os.path.join(zips, addon, 'resources'))
                except:pass
                try:shutil.copyfile(os.path.join(addon, 'resources','icon.png'),os.path.join(zips, addon, 'resources', 'icon.png'))
                except:pass
                try:shutil.copyfile(os.path.join(addon, 'resources','fanart.jpg'),os.path.join(zips, addon, 'resources', 'fanart.jpg'))
                except:pass

            xml = open(os.path.join(addon,'addon.xml'),'r').read()
            xml = re.sub('<\?xml.*','',xml)
            x.write(xml)
            x.write('\n\n')

            version = re.search('version="(.*?)"',xml).group(1)

            print color.green +  repo + ' > ' + branch + ' > '  + addon + ' > tag '  + tag + " > version "+ version+ color.end

            if addon not in  ["repository.primaeval", "repository.imdbsearch" ]:
                if tag != version:
                    print color.red +  repo + ' > ' + branch + ' > '  + addon + ' > '  + tag + " > "+ version+ color.end


            zip = addon+ "-" + version + ".zip"

            zf = zipfile.ZipFile(zip, "w")
            for dirname, subdirs, files in os.walk(addon, topdown=TypeError):
                subdirs[:] = [d for d in subdirs if d not in ['.git']]
                zf.write(dirname)
                for filename in files:
                    zf.write(os.path.join(dirname, filename))
            zf.close()

            zipdst = os.path.join(zips,addon,zip)
            try: os.rename(zip,zipdst)
            except: pass

            if addon not in  ["repository.primaeval", "repository.imdbsearch" ]:
                subprocess.call(["git","checkout","master"],cwd=addon)
                subprocess.call(["git","branch","-D","temp"],cwd=addon)



    x.write('</addons>\n')
    x.close()

    md = md5.new()
    md.update(open(addon_xml,'rb').read())
    hex = md.hexdigest()
    m = open(addon_xml +'.md5','w')
    m.write(hex)
    m.close()

f = open('.gitignore','w')
f.write('\n'.join(sorted(all_addons)))
f.close()