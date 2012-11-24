#
# core.py
#
# Copyright (C) 2012 Calum Lind <calumlind@gmail.com>
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
from deluge.common import windows_check, osx_check

if windows_check():
    import thread
    import ctypes
    from win32security import OpenProcessToken, LookupPrivilegeValue, AdjustTokenPrivileges
    from win32api import InitiateSystemShutdown, GetCurrentProcess, GetPwrCapabilities
    from ntsecuritycon import TOKEN_ADJUST_PRIVILEGES, TOKEN_QUERY, SE_SHUTDOWN_NAME, SE_PRIVILEGE_ENABLED
elif osx_check()
    #import subprocess
    pass
else:
    import dbus
    # Freedesktop Constants
    UPOWER = "org.freedesktop.UPower"
    UPOWER_PATH = "/org/freedesktop/UPower"
    POWERMAN = 'org.freedesktop.PowerManagement'
    POWERMAN_PATH = '/org/freedesktop/PowerManagement'

SYSTEM_STATES = {
    "suspend": _("Suspend"),
    "hibernate": _("Hibernate"),
    "shutdown": _("Shutdown"),
}

DEFAULT_PREFS = {
    "enabled"           : True,
    "system_state"      : None,
    "can_hibernate"     : False,
    "can_suspend"       : False
}

class Core(CorePluginBase):
    def enable(self):
        log.debug("[AutoShutDown] Enabling Plugin...")
        if osx_check():
            log.debug("[AutoShutDown] OSX not currently supported")
            #Using subprocess could call osascript
            #subprocess.call(['osascript', '-e', 'tell app "System Events" to shut down'])
            self.disable()

        if not windows_check():
            self.bus_name = UPOWER
            bus_path = UPOWER_PATH
            try:
                bus = dbus.SystemBus()
                self.bus_obj = bus.get_object(bus_name, bus_path)
            except:
                log.debug("[AutoShutDown] Fallback to older dbus PowerManagement")
                self.bus_name = POWERMAN
                bus_path = POWERMAN_PATH
                bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
                self.bus_obj = bus.get_object(bus_name, bus_path)

            self.bus_iface = dbus.Interface(bus_obj, bus_name)
            self.bus_iface_props = dbus.Interface(bus_obj, 'org.freedesktop.DBus.Properties')

        self.config = deluge.configmanager.ConfigManager("autoshutdown.conf", DEFAULT_PREFS)
        self.check_suspend_hibernate_flags()

        component.get("AlertManager").register_handler("torrent_finished_alert",
                                                        self.on_alert_torrent_finished)

    def disable(self):
        log.debug("[AutoShutDown] Disabling AutoShutDown...")
        component.get("AlertManager").deregister_handler(self.on_alert_torrent_finished)
        self.config.save()

    def on_alert_torrent_finished(self, alert):
        log.debug("[AutoShutDown] Update for every torrent finished")

        # calc how many of torrent right now
        downloading_torrents = component.get("Core").get_torrents_status({"state": "Downloading"}, ["name"])
        #all_torrents = component.get("TorrentManager").get_torrent_list()
        #self.total_torrents = len(all_torrents)
        log.info("Now total torrents:%s", len(downloading_torrents))

        # Get the torrent_id
        #torrent_id = str(alert.handle.info_hash())
        # reduce total by one
        log.debug("[AutoShutDown] %s is finished..%s", alert.handle.info_hash(), len(downloading_torrents))

        # when the number of all torrents is 0, then poweroff.
        if not downloading_torrents:
            self.power_action()

    def power_action(self):
        if not self.config["enabled"]:
            log.debug("[AutoShutDown] Disabled, nothing to do")
            return
        if self.config["system_state"] == 'shutdown':
            self.shutdown()
        elif self.config["system_state"] == 'hibernate':
            self.hibernate()
        elif self.config["system_state"] == 'suspend':
            self.suspend()

    def suspend(self):
            log.debug("[AutoShutDown] Suspending...")
            if windows_check():
                bForceClose=False
                hibernate = False
                self.adjust_windows_shutdown_privileges()
                thread.start_new_thread(
                    ctypes.windll.Powrprof.SetSuspendState, (hibernate, bForceClose, False)
                )
            else:
                self.bus_iface.Suspend()

    def hibernate(self):
            log.debug("[AutoShutDown] Hibernating...")
            if windows_check():
                bForceClose=False
                hibernate = True
                self.adjust_windows_shutdown_privileges()
                thread.start_new_thread(
                    ctypes.windll.Powrprof.SetSuspendState, (hibernate, bForceClose, False)
                )
            else:
                self.bus_iface.Hibernate()

    def shutdown(self):
            log.debug("[AutoShutDown] Shutting down...")
            if windows_check():
                timeout = 10
                message = "Deluge AutoShutdown Plugin shutting down the system after %s secs.\
                    This can be cancelled by entering 'shutdown -a' in the Run box\
                " % timeout
                self.adjust_windows_shutdown_privileges()
                InitiateSystemShutdown(None, message, timeout, 1, 0)
            else:
                self.bus_iface.Shutdown()

    def adjust_windows_shutdown_privileges(self):
        if not windows_check():
            log.error("Only usable on Windows platform")
            return
        flags = TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY
        htoken = OpenProcessToken(GetCurrentProcess(), flags)
        id = LookupPrivilegeValue(None, SE_SHUTDOWN_NAME)
        newPrivileges = [(id, SE_PRIVILEGE_ENABLED)]
        AdjustTokenPrivileges(htoken, 0, newPrivileges)

    def check_suspend_hibernate_flags()
        self.config["can_hibernate"] = False
        self.config["can_suspend"] = False
        if windows_check():
            pwr_states = GetPwrCapabilities()
            try:
                if pwr_states['HiberFilePresent'] and pwr_states['SystemS4']:
                    self.config["can_hibernate"] = True
                if pwr_states['SystemS1'] | pwr_states['SystemS2'] | pwr_states['SystemS3']:
                    self.config["can_suspend"] = True
            except KeyError, e:
                log.error("[AutoShutdown] Error reading system power capabilities: %s", e
        else:
            # Possibly should also check SuspendAllowed and HibernateAllowed for permissions
            try:
                self.config["can_suspend"] = bool(self.bus_iface_props.Get(self.bus_name, 'CanSuspend'))
                self.config["can_hibernate"] = bool(self.bus_iface_props.Get(self.bus_name, 'CanHibernate'))
            except:
                log.error("Unable to determine Suspend or Hibernate flags")
                #alternative if powerman does not work?
                #/org/freedesktop/PowerManagement org.freedesktop.PowerManagement.CanSuspend
        log.debug("[AutoShutDown] Set Power Flags, Suspend: %s, Hibernate: %s",
                    self.config["can_hibernate"], self.config["can_suspend"])

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
