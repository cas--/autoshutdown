#!/bin/bash
cd /home/ray/work/svn/raychen/python/deluge/autoshutdown
mkdir temp
export PYTHONPATH=./temp
python setup.py build develop --install-dir ./temp
cp ./temp/AutoShutdown.egg-link /home/ray/.config/deluge/plugins
rm -fr ./temp
