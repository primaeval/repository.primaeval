#!/bin/bash
set -x


branches="
master_jarvis
jarvis
master_krypton
krypton
"

krypton="
script.tvguide.fullscreen
script.tvguide.fullscreen.skin.carnelian
script.tvguide.fullscreen.skin.lapis
script.tvguide.fullscreen.skin.onyx
skin.confluence.wall
"

master_krypton="
script.tvguide.fullscreen.skin.tycoo
script.tvguide.fullscreen.skin.kjb85
skin.estuary.wall
"

master_jarvis="
context.simple.favourites
plugin.audio.bbc
plugin.audio.favourites
plugin.program.downloader
plugin.program.fixtures
plugin.program.simple.favourites
plugin.video.addons.ini.creator
plugin.video.addons.ini.player
plugin.video.bbc
plugin.video.bbc.live
plugin.video.boilerroom
plugin.video.favourites
plugin.video.hls.playlist.player
plugin.video.playlist.player
plugin.video.pvr.plugin.player
plugin.video.rageagain.again
plugin.video.replay
plugin.video.stream.searcher
plugin.video.tvlistings
plugin.video.tvlistings.xmltv
plugin.video.tvlistings.yo
script.games.play.mame
script.skin.tightener
script.tvguide.fullscreen
script.tvguide.fullscreen.skin.carnelian
script.tvguide.fullscreen.skin.lapis
script.tvguide.fullscreen.skin.onyx
script.webgrab
skin.confluence.wall
skin.naked
"

jarvis="
script.tvguide.fullscreen.skin.tycoo
script.tvguide.fullscreen.skin.kjb85
"

for branch in jarvis krypton; do
	mkdir $branch
	echo "<?xml version="1.0" encoding="UTF-8" standalone="yes"?>" > $branch/addons.xml
	echo "<addons>" >> $branch/addons.xml
done

rm .gitignore
for raw_branch in $branches; do
	echo $raw_branch
	branch=${raw_branch#*_}
	mkdir $branch

	if [ $raw_branch == "master_jarvis" ] ; then
		tail -n+2 jarvis/repository.primaeval/addon.xml >> jarvis/addons.xml
		tail -n+2 jarvis/repository.imdbsearch/addon.xml >> jarvis/addons.xml
	fi
	for addon in ${!raw_branch}; do
		echo $addon
		echo /$addon >> .gitignore
		git clone https://github.com/primaeval/$addon.git
		cd $addon/
		git fetch
		branchname=${raw_branch%_*}
		echo $branchname
		git checkout $branchname
		git pull
		tag=$(git describe --abbrev=0 --tags)
		git checkout $tag
		cd -
		mkdir $branch/$addon/
		for file in addon.xml changelog.txt icon.png fanart.jpg; do
			cp $addon/$file $branch/$addon/
		done
		if [ $branch == "krypton" ] ; then
			mkdir $branch/$addon/resources/
			for file in icon.png fanart.jpg screenshot*.jpg; do
				cp $addon/resources/$file $branch/$addon/resources/
			done
			for file in screenshot*.png; do
				cp $addon/$file $branch/$addon/
			done
		fi
		rm $branch/$addon/$addon-*.zip
		/c/Program\ Files/7-Zip/7z.exe a -xr@exclude $branch/$addon/$addon-${tag#v}.zip $addon
		tail -n+2 $addon/addon.xml >> $branch/addons.xml
	done
done

for branch in jarvis krypton ; do
	echo "</addons>" >> $branch/addons.xml
	(cd $branch && md5sum addons.xml > addons.xml.md5)
done

