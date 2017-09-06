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
"

master_krypton="
"

master_jarvis="
script.tvguide.fullscreen
"

jarvis="
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

