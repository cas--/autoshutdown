#
# core.py
#
# Copyright (C) 2009 Ray Chen <chenrano2002@gmail.com>
#
# Basic plugin template created by:
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
# Copyright (C) 2007-2009 Andrew Resch <andrewresch@gmail.com>
# Copyright (C) 2009 Damien Churchill <damoxc@gmail.com>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
# 	The Free Software Foundation, Inc.,
# 	51 Franklin Street, Fifth Floor
# 	Boston, MA  02110-1301, USA.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#

from deluge.log import LOG as log
from deluge.plugins.pluginbase import CorePluginBase
import deluge.component as component
import deluge.configmanager
from deluge.core.rpcserver import export

DEFAULT_PREFS = {
    "enable_shutdown" : True,
    "enable_hibernate" : False,
}

class Core(CorePluginBase):
    def enable(self):
        log.debug("Enable AutoShutDown")
        self.config = deluge.configmanager.ConfigManager("autoshutdown.conf", DEFAULT_PREFS)
        component.get("AlertManager").register_handler("torrent_finished_alert",
                                                        self.on_alert_torrent_finished)

    def disable(self):
        log.debug("Disable AutoShutDown")
        component.get("AlertManager").deregister_handler(self.on_alert_torrent_finished)
        self.config.save()

    def on_alert_torrent_finished(self, alert):
        log.debug("Alter for every torrent finished")

	# cal how many of torrent right now
        all_torrents = component.get("TorrentManager").get_torrent_list()
        self.total_torrents = len(all_torrents)
	log.info("Now total torrents:%s", self.total_torrents)

        # Get the torrent_id
        torrent_id = str(alert.handle.info_hash())
        # reduce one
        self.total_torrents = self.total_torrents - 1
        log.debug("%s is finished..%s", torrent_id, self.total_torrents)

        # when the number of all torrents is 0, then poweroff.
        if self.total_torrents == 0 :
            self.begin_to_poweroff()

    def begin_to_poweroff(self):
        log.debug("begin to poweroff...")

        import dbus
        bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
        devobj = bus.get_object('org.freedesktop.PowerManagement',
                                '/org/freedesktop/PowerManagement')
        self.dev = dbus.Interface(devobj, "org.freedesktop.PowerManagement")

        if self.config["enable_shutdown"]:
            log.debug("begin to Shutdown...")
            self.dev.Shutdown()

        if self.config["enable_hibernate"]:
            log.debug("begin to Hibernate...")
            self.dev.Hibernate()

    def update(self):
        pass

    @export
    def set_config(self, config):
        "sets the config dictionary"
        for key in config.keys():
            self.config[key] = config[key]
        self.config.save()

    @export
    def get_config(self):
        "returns the config dictionary"
        return self.config.config
