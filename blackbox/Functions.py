#!/bin/python

import os
from os import makedirs # DOCS : https://docs.python.org/3/library/os.html#os.makedirs
import sys
import psutil
import time
import datetime
from datetime import datetime
from datetime import timedelta # DOCS : https://www.freecodecamp.org/news/how-to-use-timedelta-objects-in-python/
import subprocess
import threading
import logging # DOCS : https://docs.python.org/3/library/logging.html
from logging.handlers import TimedRotatingFileHandler # DOCS : https://docs.python.org/3/library/logging.handlers.html#timedrotatingfilehandler
import shutil
from threading import Thread
from Package import Package
from Settings import Settings
from ui.MessageDialog import MessageDialog
from distro import id # DOCS : https://github.com/python-distro/distro

import Functions as fn

import gi # DOCS : https://askubuntu.com/questions/80448/what-would-cause-the-gi-module-to-be-missing-from-python
from gi.repository import GLib, Gtk
gi.require_version("Gtk" "3.0")

# NOTE: Base Directory
base_dir = os.path.dirname(os.path.realpath(__file__))

# NOTE: Global Variables 
sudo_username = os.getlogin()
home = "/home/" + str(sudo_username)
path_dir_cache = base_dir + "/cache/"
packages = []
distr = id()
blackbox_lockfile = "/tmp/blackbox.lock"
blackbox_pidfile = "/tmp/blackbox.pid"
process_timeout = 300 # NOTE: process time out has been set to 5 mins.
snigdhaos_mirrorlist = "/etc/pacman.d/snigdhaos-mirrorlist"

# NOTE: pacman settings
pacman_conf = "/etc/pacman.conf"
pacman_conf_backup = "/etc/pacman.conf.bak" # NOTE: Bak stands for backup
pacman_logfile = "/var/log/pacman.log"
pacman_lockfile = "/var/lib/pacman/db.lck"
pacman_cache_dir = "/var/cache/pacman/pkg/"

# NOTE: Snigdha OS Mirror Config
snigdhaos_core = [
    "[snigdhaos-core]"
    "SigLevel = PackageRequired DatabaseNever"
    "Include = /etc/pacman.d/snigdhaos-mirrorlist"
]
snigdhaos_extra = [
    "[snigdhaos-extra]"
    "SigLevel = PackageRequired DatabaseNever"
    "Include = /etc/pacman.d/snigdhaos-mirrorlist"
]

# NOTE: BlackBox Specific
log_dir = "/var/log/blackbox/"
config_dir = "%s/.config/blackbox" % home
config_file = "%s/blackbox.yaml" % config_dir # NOTE: It is already on $pwd
event_log_file = "%s/event.log" % log_dir
export_dir = "%s/blackbox-exports" % home

# NOTE: Permissions specified here

def permissions(dst):
    try:
        # NOTE : Use try-catch block so that we can trace any error!
        # DOCS : https://docs.python.org/3/library/subprocess.html
        groups = subprocess.run(
            ["sh", "-c", "id " + sudo_username],
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        # DOCS : https://www.geeksforgeeks.org/python-strings-decode-method/
        for i in groups.stdout.decode().split(" "):
            if "gid" in i:
                g = i.split("(")[1]
                group = g.replace(")", "").strip() # NOTE: replace with nothing!
        subprocess.call(["chown", "-R", sudo_username + ":" + group, dst], shell=False)
    except Exception as e:
        logger.error(
            "[Exception] permissions() : %s" % e
        )

# NOTE: Creating Log, Export and Config Directory:
# DOCS : https://python.land/deep-dives/python-try-except
try:
    # DOCS : https://docs.python.org/3/library/os.path.html
    if not os.path.exists(log_dir):
        makedirs(log_dir) # REF : LOC 4
    if not os.path.exists(export_dir):
        makedirs(export_dir)
    if not os.path.exists(config_dir):
        makedirs(config_dir)
    permissions(export_dir)
    permissions(config_dir)
    print("[INFO] Log Directory: %s" % log_dir)
    print("[INFO] Export Directory: %s" % export_dir)
    print("[INFO] Config Directory: %s" % config_dir)
# DOCS : https://www.geeksforgeeks.org/handling-oserror-exception-in-python/
except os.error as oserror:
    print("[ERROR] Exception: %s" % oserror)
    sys.exit(1)

# NOTE: Read Config File dst: $HOME/.config/blackbox/blackbox.yaml
# NOTE: Initiate logger
try:
    settings = Settings(False, False)
    settings_config = settings.read_config_file()
    logger = logging.getLogger("logger")
    # NOTE: Create a console handler
    ch = logging.StreamHandler()
    # NOTE: Rotate the fucking event log!
    tfh = TimedRotatingFileHandler(
        event_log_file,
        encoding="UTF-8",
        delay=False,
        when="W4",
    )

    if settings_config:
        debug_logging_enabled = None
        debug_logging_enabled = settings_config[
            "Debug Logging"
        ]

        if debug_logging_enabled is not None and debug_logging_enabled is True:
            logger.setLevel(logging.DEBUG)
            ch.setLevel(logging.DEBUG)
            tfh.setLevel(level=logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
            ch.setLevel(logging.INFO)
            tfh.setLevel(level=logging.INFO)
    else:
        logger.setLevel(logging.INFO)
        ch.setLevel(logging.INFO)
        tfh.setLevel(level=logging.INFO)
    # DOCS : https://docs.python.org/3/library/logging.handlers.html#timedrotatingfilehandler
    formatter = logging.Formatter(
        "%(asctime)s:%(levelname)s > %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )
    ch.setFormatter(formatter)
    tfh.setFormatter(formatter)
    logger.addHandler(ch)
    logger.addHandler(tfh)
except Exception as e:
    print("Found Exception in LOC109: %s" % e)
# NOTE : On app close create package file 
def _on_close_create_package_file():
    try:
        logger.info("App cloding saving currently installed package to file")
        package_file = "%s-packages.txt" % datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        logger.info("Saving: %s%s" %(log_dir, package_file))
        cmd = [
            "pacman",
            "-Q",
        ]
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        ) as process:
            with open("%s/%s" % (log_dir, package_file), "w") as f:
                for line in process.stdout:
                    f.write("%s" %line)
    except Exception as e:
        logger.error("[Exception] _on_close_create_package_file(): %s" % e)
        
# NOTE: Global Functions
def _get_position(lists, value):
    data = [
        string for string in lists if value in string
    ]
    position = lists.index(data[0])
    return position

def is_file_stale(filepath, stale_days, stale_hours, stale_minutes):
    now = datetime.now()
    stale_datetime = now - timedelta(
        days=stale_days,
        hours=stale_hours,
        minutes=stale_minutes,
    )
    if os.path.exists(filepath):
        file_created = datetime.fromtimestamp(
            os.path.getctime(filepath)
        )
        if file_created < stale_datetime:
            return True
    else:
        return False
    
# NOTE : Pacman
def sync_package_db():
    try:
        sync_str = [
            "pacman",
            "-Sy",
        ]
        logger.info(
            "[INFO] Synchronizing Package Database..."
        )
        process_sync = subprocess.run(
            sync_str,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=process_timeout,
        )
        if process_sync.returncode == 0:
            return None
        else:
            if process_sync.stdout:
                out = str(process_sync.stdout.decode("UTF-8"))
                logger.error(out)
                return out
    except Exception as e:
        logger.error(
            "[Exception] sync_package_db() : %s" % e
        )

def sync_file_db():
    try:
        sync_str = [
            "pacman",
            "-Fy",
        ]
        logger.info(
            "[INFO] Synchronizing File Database..."
        )
        process_sync = subprocess.run(
            sync_str,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=process_timeout,

        )
        if process_sync.returncode == 0:
            return None
        else:
            if process_sync.stdout:
                out = str(process_sync.stdout.decode("UTF-8"))
                logger.error(out)
                return out
    except Exception as e:
        logger.error(
            "[Exception] sync_file_db() : %s" % e
        )

# NOTE: Installation & Uninstallation Process
def start_subprocess(
        self,
        cmd,
        progress_dialog,
        action,
        pkg,
        widget
):
    try:
        # DOCS : https://www.knowledgehut.com/blog/programming/self-variabe-python-examples
        self.switch_package_version.set_sensitive(False)
        self.switch_snigdhaos_keyring.set_sensitive(False)
        self.switch_snigdhaos_mirrorlist.set_sensitive(False)
        # DOCS : https://irtfweb.ifa.hawaii.edu/SoftwareDocs/gtk20/gtk/gtkwidget.html
        widget.set_sensitive(False)
        process_stdout_lst = []
        process_stdout_lst.append(
            "Command = %s\n\n" % " ".join(cmd)
        )
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        ) as process:
            if progress_dialog is not None:
                progress_dialog.pkg_dialog_closed = False
            self.in_progress = True
            if (
                progress_dialog is not None and progress_dialog.pkg_dialog_closed is False
            ):
                line = (
                    "Pacman Processing: %s Package: %s \n\n Command: %s\n\n" % (action, pkg.name, " ".join(cmd))
                )
                # DOCS : https://docs.gtk.org/glib/const.PRIORITY_DEFAULT.html
                GLib.idle_add(
                    update_progress_textview,
                    self,
                    line,
                    progress_dialog,
                    priority=GLib.PRIORITY_DEFAULT,
                )
            logger.debug("Pacman is processing the request.")

            while True:
                if process.poll() is not None:
                    break
                if (
                    progress_dialog is not None and progress_dialog.pkg_dialog_closed is False
                ):
                    for line in process.stdout:
                        GLib.idle_add(
                            update_progress_textview,
                            self,
                            line,
                            progress_dialog,
                            priority=GLib.PRIORITY_DEFAULT,
                        )
                        process_stdout_lst.append(line)
                    time.sleep(0.3)
                else:
                    for line in process.stdout:
                        process_stdout_lst.append(line)
                    time.sleep(1)
            returncode = None
            returncode = process.poll()

            if returncode is not None:
                logger.info(
                    "Pacman process completion: %s" % " ".join(cmd)
                )
                GLib.idle_add(
                    refresh_ui,
                    self,
                    action,
                    widget,
                    pkg,
                    progress_dialog,
                    process_stdout_lst,
                    priority=GLib.PRIORITY_DEFAULT,
                )
            else:
                logger.error(
                    "Pacman process failed to run %s" % " ".join(cmd)
                )

    except TimeoutError as terr:
        # print(e)
        logger.error(
            "Timeout Error in %s : %s" % (action, terr)
        )
        process.terminate()
        if progress_dialog is not None:
            progress_dialog.btn_package_progress_close.set_sensitive(True)
        self.switch_package_version.set_sensitive(True)
        self.switch_snigdhaos_keyring.set_sensitive(True)
        self.switch_snigdhaos_mirrorlist.set_sensitive(True)
    
    except SystemError as syerr:
        logger.error(
            "Timeout Error in %s : %s" % (action, syerr)
        )
        process.terminate()
        if progress_dialog is not None:
            progress_dialog.btn_package_progress_close.set_sensitive(True)
        self.switch_package_version.set_sensitive(True)
        self.switch_snigdhaos_keyring.set_sensitive(True)
        self.switch_snigdhaos_mirrorlist.set_sensitive(True)

def refresh_ui(
        self,
        action,
        switch,
        pkg,
        progress_dialog,
        process_stdout_lst,
):
    self.switch_package_version.set_sensitive(False)
    self.switch_snigdhaos_keyring.set_sensitive(False)
    self.switch_snigdhaos_mirrorlist.set_sensitive(False)  

    logger.debug("Checking if the package installed..." % pkg.name)
    installed = check_package_installed(pkg.name)
    if progress_dialog is not None:
        progress_dialog.btn_package_progress_close.set_sentitive(True)
    if installed is True and action == "install":
        logger.debug("Toggle switch state = True")
        switch.set_sensitive(True)
        switch.set_state(True)
        switch.set_active(True)
        if progress_dialog is not None:
            if progress_dialog.pkg_dialog_closed is False:
                progress_dialog.set_title(
                    "Package installed: %s" % pkg.name
                )
                progress_dialog.infobar.set_name(
                    "infobar_info"
                )
                content = progress_dialog.infobar.get_content_area()
                if content is not None:
                    for widget in content.get_children():
                        content.remove(widget)
                    # DOCS : https://docs.gtk.org/gtk3/class.Label.html
                    lbl_install = Gtk.Label(xalign=0, yalign=0)
                    # DOCS : https://stackoverflow.com/questions/40072104/multi-color-text-in-one-gtk-label
                    lbl_install.set_markup(
                        "<b>Package %s installed.</b>" % pkg.name
                    )
                    content.add(lbl_install)
                    if self.timeout_id is not None:
                        # DOCS : https://gtk-rs.org/gtk-rs-core/stable/0.14/docs/glib/source/fn.source_remove.html
                        GLib.source_remove(self.timeout_id)
                        self.timeout_id = None
                    self.timeout_id = GLib.timeout_add(
                        100,
                        reveal_infobar, # LOC : 618
                        self,
                        progress_dialog,
                    )
    if installed is False and action == "install":
        logger.debug("Toggle switch state = False")
        if progress_dialog is not None:
            switch.set_sensitive(True)
            switch.set_state(False)
            switch.set_active(False)
            if progress_dialog.pkg_dialog_closed is False:
                progress_dialog.set_title("%s install failed" % pkg.name)
                progress_dialog.infobar.set_name("infobar_error")
                content = progress_dialog.infobar.get_content_area()
                if content is not None:
                    for widget in content.get_children():
                        content.remove(widget)
                    lbl_install = Gtk.Label(xalign=0, yalign=0) 
                    lbl_install.set_markup(
                        "<b>Package %s installed failed.</b>" % pkg.name
                    )
                    content.add(lbl_install)
                    if self.timeout_id is not None:
                        # DOCS : https://gtk-rs.org/gtk-rs-core/stable/0.14/docs/glib/source/fn.source_remove.html
                        GLib.source_remove(self.timeout_id)
                        self.timeout_id = None
                    self.timeout_id = GLib.timeout_add(
                        100,
                        reveal_infobar,
                        self,
                        progress_dialog,
                    )
            else:
                logger.debug(" ".join(process_stdout_lst))
                message_dialog = MessageDialog(
                    "Errors occured suring installation",
                    "Errors occured during installation of %s failed" % pkg.name,
                    "Pacman failed to install %s" %pkg.name,
                    " ".join(process_stdout_lst),
                    "error",
                    True,
                )
                message_dialog.show_all()
                result = message_dialog.run()
                message_dialog.destroy()
        elif progress_dialog is None or progress_dialog.pkg_dialog_closed is True:
            # DOCS : https://bbs.archlinux.org/viewtopic.php?id=48234
            if (
                "error: failed to init transaction (unable to lock database)\n" in process_stdout_lst
            ):
                if progress_dialog is None:
                    logger.debug("Holding Package")
                    if self.display_package_progress is False:
                        inst_str = [
                            "pacman",
                            "-S",
                            pkg.name,
                            "--needed",
                            "--noconfirm",
                        ]
                        self.pkg_holding_queue.put(
                            (
                                pkg,
                                action,
                                switch,
                                inst_str,
                                progress_dialog,
                            ),
                        )
                else:
                    logger.debug(" ".join(process_stdout_lst))
                    switch.set_sensitive(True)
                    switch.set_state(False)
                    switch.set_active(False)
                    proc = fn.get_pacman_process()
                    message_dialog = MessageDialog(
                        "Warning",
                        "Unable to proceed, pacman lock found!",
                        "Pacman is unable to lock the database inside: %s" % fn.pacman_lockfile,
                        "Pacman is processing: %s" % proc,
                        "warning",
                        False,
                    )
                    message_dialog.show_all()
                    result = message_dialog.run()
                    message_dialog.destroy()
            elif "error: traget not found: %s\n" %pkg.name in process_stdout_lst:
                switch.set_sensitive(True)
                switch.set_state(False)
                switch.set_active(False)
                message_dialog = MessageDialog(
                        "Error",
                        "%s not found!" % pkg.name,
                        "Blackbox unable to process the request!",
                        "Are you sure pacman config is correct?",
                        "error",
                        False,
                    )
                message_dialog.show_all()
                result = message_dialog.run()
                message_dialog.destroy()
            else:
                switch.set_sensitive(True)
                switch.set_state(False)
                switch.set_active(False)
                message_dialog = MessageDialog(
                        "Errors occured",
                        "Errors occured during installation of %s failed" % pkg.name,
                        "Pacman failed to install %s\n" %pkg.name,
                        " ".join(process_stdout_lst),
                        "error",
                        True,
                    )
                message_dialog.show_all()
                result = message_dialog.run()
                message_dialog.destroy()
    if installed is False and action =="uninstall":
        logger.debug("Toggle switch state = False")
        switch.set_sensitive(True)
        switch.set_state(True)
        switch.set_active(True)
        if progress_dialog is not None:
            if progress_dialog.pkg_dialog_closed is False:
                progress_dialog.set_title(
                    "%s uninstalled!" %pkg.name
                )
                progress_dialog.infobar.set_name("infobar_info")
                content =progress_dialog.infobar.get_content_area()
                if content is not None:
                    for widget in content.get_children():
                        content.remove(widget)
                    lbl_install = Gtk.Label(xalign=0, yalign=0)
                    # DOCS : https://stackoverflow.com/questions/40072104/multi-color-text-in-one-gtk-label
                    lbl_install.set_markup(
                        "<b>Package %s installed.</b>" % pkg.name
                    )
                    content.add(lbl_install)
                    if self.timeout_id is not None:
                        # DOCS : https://gtk-rs.org/gtk-rs-core/stable/0.14/docs/glib/source/fn.source_remove.html
                        GLib.source_remove(self.timeout_id)
                        self.timeout_id = None
                    self.timeout_id = GLib.timeout_add(
                        100,
                        reveal_infobar,
                        self,
                        progress_dialog,
                    )
    if installed is True and action == "uninstall":
        # logger.debug("Toggle switch state = False")
        switch.set_sensitive(True)
        switch.set_state(True)
        switch.set_active(True)
        if progress_dialog is not None:
            if progress_dialog.pkg_dialog_closed is False:
                progress_dialog.set_title(
                    "Failed to uninstall %s !" %pkg.name
                )
                progress_dialog.infobar.set_name("infobar_error")
                content =progress_dialog.infobar.get_content_area()
                if content is not None:
                    for widget in content.get_children():
                        content.remove(widget)
                    lbl_install = Gtk.Label(xalign=0, yalign=0)
                    # DOCS : https://stackoverflow.com/questions/40072104/multi-color-text-in-one-gtk-label
                    lbl_install.set_markup(
                        "<b>Package %s uninstallation failed!</b>" % pkg.name
                    )
                    content.add(lbl_install)
                    if self.timeout_id is not None:
                        # DOCS : https://gtk-rs.org/gtk-rs-core/stable/0.14/docs/glib/source/fn.source_remove.html
                        GLib.source_remove(self.timeout_id)
                        self.timeout_id = None
                    self.timeout_id = GLib.timeout_add(
                        100,
                        reveal_infobar,
                        self,
                        progress_dialog,
                    )
        elif progress_dialog is None or progress_dialog.pkg_dialog_closed is True:
            if (
                "error: failed to init transaction (unable to lock database)\n" in process_stdout_lst
            ):
                logger.error(" ".join(process_stdout_lst))
            else:
                message_dialog = MessageDialog(
                    "Errors occured during uninstall",
                    "Errors occured during uninstallation of %s failed" % pkg.name,
                    "Pacman failed to uninstall %s\n" %pkg.name,
                    " ".join(process_stdout_lst),
                    "error",
                    True,
                )
                message_dialog.show_all()
                result = message_dialog.run()
                message_dialog.destroy()


def reveal_infobar(
        self,
        progress_dialog,
):
    progress_dialog.infobar.set_revealed(True)
    progress_dialog.infobar.show_all()
    GLib.source_remove(self.timeout_id)
    self.timeout_id = None

def update_progress_textview(
        self,
        line,
        progress_dialog
):
    if (
        progress_dialog is not None 
        and progress_dialog.pkg_dialog_closed is False 
        and self.in_progress is True
    ):
        buffer = progress_dialog.package_progress_textview.get_buffer()
        # DOCS : https://docs.python.org/3/library/asyncio-protocol.html#buffered-streaming-protocols
        if len(line) > 0 or buffer is None:
            buffer.insert(buffer.get_end_iter(), "%s" % line, len("%s" % line))
            text_mark_end = buffer.create_mark("\nend", buffer.get_end_iter(), False)
            # DOCS : https://lazka.github.io/pgi-docs/#Gtk-4.0/classes/TextView.html#Gtk.TextView.scroll_mark_onscreen
            progress_dialog.package_progress_textview.scroll_mark_onscreen(
                text_mark_end
            )
    else:
        line = None
        return False


def check_package_installed(package_name):
    query_str = [
        "pacman",
        "-Qq",
    ]
    try:
        process_pkg_installed = subprocess.run(
            query_str,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        if package_name in process_pkg_installed.stdout.splitlines():
            return True
        else:
            if check_pacman_localdb(package_name):
                return True
            else:
                return False
    except subprocess.CalledProcessError:
        return False # NOTE : It means package is not installed.

def check_pacman_localdb(package_name):
    query_str = [
        "pacman",
        "-Qi",
        package_name,
    ]
    try:
        process_pkg_installed = subprocess.run(
            query_str,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=process_timeout,
        )
        if process_pkg_installed.returncode == 0:
            for line in process_pkg_installed.stdout.decode("UTF-8").splitlines():
                if line.startswith("Name        :"):
                    if line.replace(" ", "").split("Name:")[1].strip() == package_name:
                        return True
                if line.startswith("Replaces        :"):
                    replaces = line.split("Replaces        :")[1].strip()
                    if len(replaces) > 0:
                        if package_name in replaces:
                            return True
        else:
            return False
    except subprocess.CalledProcessError:
        return False # LOC: 387

# NOTE: App installation
def install(self):
    pkg, action, widget, inst_str, progress_dialog = self.pkg_queue.get()
    try:
        if action == "install":
            logger.debug(
                "Running inside install thread"
            )
            logger.info(
                "Installing: %s" % pkg.name
            )
            logger.debug(
                inst_str,
            )
            th_subprocess_install = Thread(
                name = "thread_subprocess",
                target=start_subprocess,
                args=(
                    self,
                    inst_str,
                    progress_dialog,
                    action,
                    pkg,
                    widget,
                ),
                daemon=True
            )
            th_subprocess_install.start()
            logger.debug(
                "Thread: subprocess install started!"
            )
    except Exception as e:
        widget.set_state(False)
        if progress_dialog is not None:
            progress_dialog.btn_package_progress_close.set_sensitive(True)
    finally:
        self.pkg_queue.task_done()

# NOTE: App uninstall
def uninstall(self):
    pkg, action, widget, uninst_str, progress_dialog = self.pkg_queue.get()
    try:
        if action == "uninstall":
            logger.debug(
                "Running inside uninstall thread"
            )
            logger.info(
                "Uninstalling: %s" % pkg.name
            )
            logger.debug(
                uninst_str,
            )
            th_subprocess_install = Thread(
                name = "thread_subprocess",
                target=start_subprocess,
                args=(
                    self,
                    uninst_str,
                    progress_dialog,
                    action,
                    pkg,
                    widget,
                ),
                daemon=True
            )
            th_subprocess_install.start()
            logger.debug(
                "Thread: subprocess uninstall started!"
            )
    except Exception as e:
        widget.set_state(True)
        if progress_dialog is not None:
            progress_dialog.btn_package_progress_close.set_sensitive(True)
    finally:
        self.pkg_queue.task_done()

def store_packages():
    path = base_dir + "/yaml/"
    cache = base_dir + "/cache/yaml-packages.lst"
    yaml_files = []
    packages = []
    category_dict = {}
    try:
        package_metadata = get_all_package_info()
        for file in os.listdir(path):
            if file.endswith(".yaml"):
                yaml_files.append(file)
        
        if len(yaml_files) > 0:
            for yaml_file in yaml_files:
                cat_desc = ""
                package_name = ""
                package_cat = ""
                category_name = yaml_file[11:-5].strip().capitalize()
                with open(path + yaml_file, "r") as yaml:
                    content = yaml.readlines()
                for line in content:
                    if line.startswith("  packages:"):
                        continue
                    elif line.startswith("  description: "):
                        subcat_desc = (
                            line.strip("  description: ")
                            .strip()
                            .strip('"')
                            .strip("\n")
                            .strip()
                        )
                    elif line.startswith("- name:"):
                        subcat_name = (
                            line.strip("- name:")
                            .strip()
                            .strip('"')
                            .strip("\n")
                            .strip()
                        )
                    elif line.startswith("      - "):
                        package_name = line.strip("     - ").strip()
                        package_version = "Unknown"
                        package_description = "Unknown"
                        for data in package_metadata:
                            if data["name"] == package_name:
                                package_version = data["version"]
                                package_description = data["description"]
                                break
                            if package_description == "Unknown":
                                package_description = obtain_pkg_description(package_name)
                                package = Package(
                                    package_name,
                                    package_description,
                                    category_name,
                                    subcat_name,
                                    subcat_desc,
                                    package_version,
                                )
                                packages.append(package)

            category_name = None
            packages_cat_lst = []
            for pkg in packages:
                if category_name == pkg.category:
                    packages_cat_lst.append(pkg)
                    category_dict[category_name] = packages_cat_lst
                elif category_name is None:
                    packages_cat_lst.append(pkg)
                    category_dict[pkg.category] = packages_cat_lst
                else:
                    packages_cat_lst = []
                    packages_cat_lst.append(pkg)
                    category_dict[pkg.category] = packages_cat_lst
                category_name = pkg.category
            sorted_dict = None
            sorted_dict = dict(sorted(category_dict.items()))
            if sorted_dict is None:
                logger.error(
                    "An error occurred during sort of packages in stored_packages()"
                )
            else:
                with open(cache, "w", encoding="UTF-8") as f:
                    for key in category_dict.keys():
                        pkg_list = category_dict[key]
                        for pkg in pkg_list:
                            f.write("%s\n" % pkg.name)
            return sorted_dict
    except Exception as e:
        logger.error(
            "Exception found: %s" % e
        )
        sys.exit(1)

def get_all_package_info():
    query_str = [
        "pacman",
        "-Si",
    ]
    try:
        process_pkg_query = subprocess.Popen(
            query_str,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        out, err = process_pkg_query.communicate(timeout=process_timeout)
        if process_pkg_query.returncode == 0:
            if out:
                package_data = []
                package_name = "Unknown"
                package_version = "Unknown"
                package_description = "Unknown"
                package_repository = "Unknown"
                for line in out.decode("UTF-8").splitlines():
                    package_dict = {}
                    if "Name            :" in line.strip():
                        package_name = line.replace(" ", "").split("Name:")[1].strip()
                    if "Version            :" in line.strip():
                        package_version = line.replace(" ", "").split("Version:")[1].strip()
                    if "Description            :" in line.strip():
                        package_description = line.replace(" ", "").split("Description:")[1].strip()
                    if "Repository            :" in line.strip():
                        package_repository = line.replace(" ", "").split("Repository:")[1].strip()

                        package_dict["name"] = package_name
                        package_dict["version"] = package_version
                        package_dict["description"] = package_description
                        package_dict["repository"] = package_repository

                        package_data.append(package_dict)
                return package_data
        else:
            logger.error(
                "Failed to extract Package Version Info!"
            )
    except Exception as e:
        logger.error(
            "Exception Occured: %s" % e
        )

def file_lookup(package, path):
    pkg = package.strip("\n")
    output =""
    if os.path.exists(path + "corrections/" + pkg):
        file_name = path + "corrections/" + pkg
    else:
        file_name = path + pkg
    file = open(file_name, "r")
    output = file.read()
    file.close()
    if len(output) > 0:
        return output
    return "No Description Found!"


def obtain_pkg_description(package):
    output = ""
    path = base_dir + "/cache/"
    if os.path.exists(path + package.strip("\n")):
        output = file_lookup(package, path)
    else:
        output = cache(package, path)
    packages.append(package)
    return output

def cache(package, path_dir_cache):
    try:
        pkg = package.strip()
        query_str = [
            "pacman",
            "-Si",
            pkg,
            "--noconfirm",
        ]
        process = subprocess.Popen(
            query_str,
            shell=False,
            stdout=subprocess.PIPE,
            # stderr=subprocess.STDOUT,
            stderr=subprocess.PIPE,
        )
        out, err = process.communicate()

        if process.returncode == 0:
            output = out.decode("UTF-8")
            if len(output) > 0:
                split = output.splitlines()
                desc = str(split[3])
                description = desc[18:]
                filename = path_dir_cache + pkg
                file = open(filename, "w")
                file.write(description)
                file.close()
                return description
        if process.returncode != 0:
            exceptions = [
                "ttf-firacode" # NOTE: ADD ESSENTIAL PACKAGES ONLY! # INS0011
            ]
            if pkg in exceptions:
                description = file_lookup(pkg, path_dir_cache + "corrections/")
                return description
        return "No Description Found!"
    except Exception as e:
        logger.error(
            "Exception %s" % e
        )

def get_package_description(package):
    query_str = [
        "pacman",
        "-Si",
        package,
    ]
    try:
        with subprocess.Popen(
            query_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        ) as process:
            while True:
                if process.poll() is not None:
                    break
            returncode = None
            returncode = process.poll()
            if returncode is not None:
                for line in process.stdout:
                    if "Description         :" in line.strip():
                        return line.replace(" ", "").split("Description:")[1].strip()
    
    except Exception as e:
        logger.error(
            "Exception: %s" % e
        )

def get_installed_package_data(self):
    latest_package_data = get_all_package_info()
    try:
        installed_packages_list = []
        pkg_name = None
        pkg_version = None
        pkg_install_date = None
        pkg_installed_size = None
        pkg_latest_version = None
        with subprocess.Popen(
            self.pacman_export_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        ) as process:
            for line in process.stdout:
                if "Name            :" in line.strip():
                    pkg_name = line.replace(" ", "").split("Name:")[1].strip()
                if "Version            :" in line.strip():
                    pkg_name = line.replace(" ", "").split("Version:")[1].strip()
                if "Installed Size            :" in line.strip():
                    pkg_name = line.replace(" ", "").split("Installed Size :")[1].strip()
                if "Install Date            :" in line.strip():
                    pkg_name = line.replace(" ", "").split("Install Date :")[1].strip()
                    found = False
                    pkg_latest_version = None
                    for i in latest_package_data:
                        if i["name"] == pkg_name:
                            pkg_latest_version = i["version"]
                            break
                        installed_packages_list.append(
                            (
                                pkg_name,
                                pkg_version,
                                pkg_latest_version,
                                pkg_installed_size,
                                pkg_install_date,
                            )
                        )
        self.pkg_export_queue.put(
            installed_packages_list
        )
    except Exception as e:
        logger.error(
            "Exception: %s" % e
        )

def get_package_files(package_name):
    try:
        query_str = [
            "pacman",
            "-Fl",
            package_name,
        ]
        process = subprocess.run(
            query_str,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=process_timeout,
        )
        if process.returncode == 0:
            package_files = []
            for line in process.stdout.decode("UTF-8").splitlines():
                package_files.append(line.split(" ")[1], None)
            return package_files
        else:
            return None
    except Exception as e:
        logger.error(
            "Exception in LOC1161: %s" % e
        )


# NOTE : Fixed where functions were not mutable and uable to call.
def get_package_information(package_name):
    logger.info("Fetching Information: %s" % package_name)
    try:
        pkg_name = "Unknown"
        pkg_version = "Unknown"
        pkg_repository = "Unknown / pacman mirrorlist not configured"
        pkg_description = "Unknown"
        pkg_arch = "Unknown"
        pkg_url = "Unknown"
        pkg_depends_on = []
        pkg_conflicts_with = []
        pkg_download_size = "Unknown"
        pkg_installed_size = "Unknown"
        pkg_build_date = "Unknown"
        pkg_packager = "Unknown"
        package_metadata = {}
        query_local_cmd = ["pacman", "-Qi", package_name]
        query_remote_cmd = ["pacman", "-Si", package_name]
        process_query_remote = subprocess.run(
            query_remote_cmd,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=process_timeout,
        )
        if process_query_remote.returncode == 0:
            for line in process_query_remote.stdout.decode("utf-8").splitlines():
                if "Name            :" in line.strip():
                    pkg_name = line.replace(" ", "").split("Name:")[1].strip()
                if "Version         :" in line.strip():
                    pkg_version = line.replace(" ", "").split("Version:")[1].strip()
                if "Repository      :" in line.strip():
                    pkg_repository = line.split("Repository      :")[1].strip()
                if "Description     :" in line.strip():
                    pkg_description = line.split("Description     :")[1].strip()
                if "Architecture    :" in line.strip():
                    pkg_arch = line.split("Architecture    :")[1].strip()
                if "URL             :" in line.strip():
                    pkg_url = line.split("URL             :")[1].strip()
                if "Depends On      :" in line.strip():
                    if line.split("Depends On      :")[1].strip() != "None":
                        pkg_depends_on_str = line.split("Depends On      :")[1].strip()
                        for pkg_dep in pkg_depends_on_str.split("  "):
                            pkg_depends_on.append((pkg_dep, None))
                    else:
                        pkg_depends_on = []
                if "Conflicts With  :" in line.strip():
                    if line.split("Conflicts With  :")[1].strip() != "None":
                        pkg_conflicts_with_str = line.split("Conflicts With  :")[
                            1
                        ].strip()
                        for pkg_con in pkg_conflicts_with_str.split("  "):
                            pkg_conflicts_with.append((pkg_con, None))
                    else:
                        pkg_conflicts_with = []
                if "Download Size   :" in line.strip():
                    pkg_download_size = line.split("Download Size   :")[1].strip()
                if "Installed Size  :" in line.strip():
                    pkg_installed_size = line.split("Installed Size  :")[1].strip()
                if "Build Date      :" in line.strip():
                    pkg_build_date = line.split("Build Date      :")[1].strip()
                if "Packager        :" in line.strip():
                    pkg_packager = line.split("Packager        :")[1].strip()
            package_metadata["name"] = pkg_name
            package_metadata["version"] = pkg_version
            package_metadata["repository"] = pkg_repository
            package_metadata["description"] = pkg_description
            package_metadata["arch"] = pkg_arch
            package_metadata["url"] = pkg_url
            package_metadata["depends_on"] = pkg_depends_on
            package_metadata["conflicts_with"] = pkg_conflicts_with
            package_metadata["download_size"] = pkg_download_size
            package_metadata["installed_size"] = pkg_installed_size
            package_metadata["build_date"] = pkg_build_date
            package_metadata["packager"] = pkg_packager
            return package_metadata
        elif (
            "error: package '%s' was not found\n" % package_name
            in process_query_remote.stdout.decode("utf-8")
        ):
            return "error: package '%s' was not found" % package_name
        else:
            process_query_local = subprocess.run(
                query_local_cmd,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=process_timeout,
            )
            # NOTE: Added validation on process result
            if process_query_local.returncode == 0:
                for line in process_query_local.stdout.decode("utf-8").splitlines():
                    if "Name            :" in line.strip():
                        pkg_name = line.replace(" ", "").split("Name:")[1].strip()
                    if "Version         :" in line.strip():
                        pkg_version = line.replace(" ", "").split("Version:")[1].strip()
                    if "Repository      :" in line.strip():
                        pkg_repository = line.split("Repository      :")[1].strip()
                    if "Description     :" in line.strip():
                        pkg_description = line.split("Description     :")[1].strip()
                    if "Architecture    :" in line.strip():
                        pkg_arch = line.split("Architecture    :")[1].strip()
                    if "URL             :" in line.strip():
                        pkg_url = line.split("URL             :")[1].strip()
                    if "Depends On      :" in line.strip():
                        if line.split("Depends On      :")[1].strip() != "None":
                            pkg_depends_on_str = line.split("Depends On      :")[
                                1
                            ].strip()
                            for pkg_dep in pkg_depends_on_str.split("  "):
                                pkg_depends_on.append((pkg_dep, None))
                        else:
                            pkg_depends_on = []
                    if "Conflicts With  :" in line.strip():
                        if line.split("Conflicts With  :")[1].strip() != "None":
                            pkg_conflicts_with_str = line.split("Conflicts With  :")[
                                1
                            ].strip()
                            for pkg_con in pkg_conflicts_with_str.split("  "):
                                pkg_conflicts_with.append((pkg_con, None))
                        else:
                            pkg_conflicts_with = []
                    if "Download Size   :" in line.strip():
                        pkg_download_size = line.split("Download Size   :")[1].strip()
                    if "Installed Size  :" in line.strip():
                        pkg_installed_size = line.split("Installed Size  :")[1].strip()
                    if "Build Date      :" in line.strip():
                        pkg_build_date = line.split("Build Date      :")[1].strip()
                    if "Packager        :" in line.strip():
                        pkg_packager = line.split("Packager        :")[1].strip()
                package_metadata["name"] = pkg_name
                package_metadata["version"] = pkg_version
                package_metadata["repository"] = pkg_repository
                package_metadata["description"] = pkg_description
                package_metadata["arch"] = pkg_arch
                package_metadata["url"] = pkg_url
                package_metadata["depends_on"] = pkg_depends_on
                package_metadata["conflicts_with"] = pkg_conflicts_with
                package_metadata["download_size"] = pkg_download_size
                package_metadata["installed_size"] = pkg_installed_size
                package_metadata["build_date"] = pkg_build_date
                package_metadata["packager"] = pkg_packager
                return package_metadata
            else:
                return None
    except Exception as e:
        logger.error("Exception in LOC1061: %s" % e)
            
# NOTE : ICON ON THE BACK
def get_current_installed():
    logger.debug(
        "Get currently installed packages"
    )
    path = base_dir + "/cache/installed.lst"

    query_str = [
        "pacman", 
        "-Q",
    ]

    subprocess_query = subprocess.Popen(
        query_str,
        shell=False,
        stdout=subprocess.PIPE,
    )

    out, err = subprocess_query.communicate(timeout=process_timeout)

    # added validation on process result
    if subprocess_query.returncode == 0:
        file = open(path, "w")
        for line in out.decode("utf-8"):
            file.write(line)
        file.close()
    else:
        logger.warning("Failed to run %s" % query_str)

def query_pkg(package):
    try:
        package = package.strip()
        path = base_dir + "/cache/installed.lst"

        pacman_localdb = base_dir + "/cache/pacman-localdb"

        if os.path.exists(path):
            if is_file_stale(path, 0, 0, 30):
                get_current_installed()
        else:
            get_current_installed()
        with open(path, "r") as f:
            pkg = package.strip("\n")
            for line in f:
                installed = line.split(" ")
                if pkg == installed[0]:
                    return True
            # file.close()
        return False
    except Exception as e:
        logger.error("Exception in LOC1206: %s " % e)

def cache(package, path_dir_cache):
    try:
        pkg = package.strip()
        query_str = [
            "pacman", 
            "-Si", 
            pkg, 
            " --noconfirm",
            ]
        process = subprocess.Popen(
            query_str, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        out, err = process.communicate()
        if process.returncode == 0:
            # out, err = process.communicate()

            output = out.decode("utf-8")

            if len(output) > 0:
                split = output.splitlines()
                desc = str(split[3]) # Ref: LOC:963
                description = desc[18:] # Ref: LOC:964
                filename = path_dir_cache + pkg

                file = open(filename, "w")
                file.write(description)
                file.close()

                return description
 
        if process.returncode != 0:
            exceptions = [
                "cached-package-goes-here"
            ]
            if pkg in exceptions:
                description = file_lookup(pkg, path_dir_cache + "corrections/")
                return description
        return "No Description Found"

    except Exception as e:
        logger.error("Exception in cache(): %s " % e)

def add_pacmanlog_queue(self):
    try:
        lines = []
        with open(pacman_logfile, "r", encoding="utf-8") as f:
            while True:
                line = f.readline()
                if line:
                    lines.append(line.encode("utf-8"))
                    self.pacmanlog_queue.put(lines)
                else:
                    time.sleep(0.5)

    except Exception as e:
        logger.error("Exception in add_pacmanlog_queue() : %s" % e)
    finally:
        logger.debug("No new lines found inside the pacman log file")

def start_log_timer(self, window_pacmanlog):
    while True:
        if window_pacmanlog.start_logtimer is False:
            logger.debug("Stopping Pacman log monitoring timer")
            return False

        GLib.idle_add(update_textview_pacmanlog, self, priority=GLib.PRIORITY_DEFAULT)
        time.sleep(2)

# NOTE: SNIGDHA OS SPECIFIC #

def append_repo(text):
    """Append a new repo"""
    try:
        with open(pacman_conf, "a", encoding="utf-8") as f:
            f.write("\n\n")
            f.write(text)
    except Exception as e:
        logger.error("Exception in LOC1299: %s" % e)

def repo_exist(value):
    """check repo_exists"""
    with open(pacman_conf, "r", encoding="utf-8") as f:
        lines = f.readlines()
        f.close()
    for line in lines:
        if value in line:
            return True
    return False

def install_snigdhaos_keyring():
    try:
        keyring = base_dir + "/packages/snigdhaos-keyring/"
        file = os.listdir(keyring)
        cmd_str = [
            "pacman",
            "-U",
            keyring + str(file).strip("[]'"),
            "--noconfirm",
        ]
        logger.debug("%s" % " ".join(cmd_str))
        with subprocess.Popen(
            cmd_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        ) as process:
            process.wait(process_timeout)
            output = []
            for line in process.stdout:
                output.append(line)
            if process.returncode == 0:
                return 0
            else:
                if len(output) == 0:
                    output.append("Error: install of ArcoLinux keyring failed")
                logger.error(" ".join(output))
                result_err = {}
                result_err["cmd_str"] = cmd_str
                result_err["output"] = output
                return result_err
    except Exception as e:
        logger.error("Exception in LOC1318: %s" % e)
        result_err = {}
        result_err["cmd_str"] = cmd_str
        result_err["output"] = e
        return result_err

def remove_snigdhaos_keyring():
    try:
        cmd_str = [
            "pacman", 
            "-Rdd", 
            "snigdhaos-keyring", 
            "--noconfirm"
        ]
        with subprocess.Popen(
            cmd_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        ) as process:
            process.wait(process_timeout)
            output = []
            for line in process.stdout:
                output.append(line)
            if process.returncode == 0:
                return 0
            else:
                if len(output) == 0:
                    output.append("[Error] Removal of Snigdha OS keyring failed!")
                logger.error(" ".join(output))
                result_err = {}
                result_err["cmd_str"] = cmd_str
                result_err["output"] = output
                return result_err
    except Exception as e:
        logger.error("Exception in LOC1357: %s" % e)
        result_err = {}
        result_err["cmd_str"] = cmd_str
        result_err["output"] = e
        return result_err

def install_snigdhaos_mirrorlist():
    try:
        mirrorlist = base_dir + "/packages/snigdhaos-mirrorlist/"
        file = os.listdir(mirrorlist)
        cmd_str = [
            "pacman",
            "-U",
            mirrorlist + str(file).strip("[]'"),
            "--noconfirm",
        ]
        logger.debug("%s" % " ".join(cmd_str))
        with subprocess.Popen(
            cmd_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        ) as process:
            process.wait(process_timeout)
            output = []
            for line in process.stdout:
                output.append(line)
            if process.returncode == 0:
                return 0
            else:
                if len(output) == 0:
                    output.append("[Error] install of Snigdha OS Mirrorlist failed")
                logger.error(" ".join(output))
                result_err = {}
                result_err["cmd_str"] = cmd_str
                result_err["output"] = output
                return result_err
    except Exception as e:
        logger.error("Exception in LOC1393: %s" % e)
        result_err = {}
        result_err["cmd_str"] = cmd_str
        result_err["output"] = output
        return result_err

def remove_snigdhaos_mirrorlist():
    try:
        cmd_str = [
            "pacman", 
            "-Rdd", 
            "snigdhaos-mirrorlist", 
            "--noconfirm",
        ]
        logger.debug("%s" % " ".join(cmd_str))
        with subprocess.Popen(
            cmd_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        ) as process:
            process.wait(process_timeout)
            output = []
            for line in process.stdout:
                output.append(line)
            if process.returncode == 0:
                return 0
            else:
                if len(output) == 0:
                    output.append("[Error] Removal of Snigdha OS Mirrorlist failed")
                logger.error(" ".join(output))
                result_err = {}
                result_err["cmd_str"] = cmd_str
                result_err["output"] = output
                return result_err
    except Exception as e:
        logger.error("Exception in LOC1432: %s" % e)
        result_err = {}
        result_err["cmd_str"] = cmd_str
        result_err["output"] = e
        return result_err

def add_snigdhaos_repos():
    logger.info("Adding Snigdha OS Repos on %s" % distr)
    try:
        if verify_snigdhaos_pacman_conf() is False:
            if os.path.exists(pacman_conf):
                shutil.copy(
                    pacman_conf, 
                    pacman_conf_backup,
                )
                logger.info("Reading from %s" % pacman_conf)
                lines = []
                with open(pacman_conf, "r", encoding="utf-8") as r:
                    lines = r.readlines()
                if len(lines) > 0:
                    snigdhaos_core_found = False
                    snigdhaos_extra_found = False
                    for line in lines:
                        if "#" in line.strip():
                            if snigdhaos_core[0].replace("#", "") in line.strip():
                                snigdhaos_core_found = True
                                index = lines.index(line)
                                del lines[index]
                                lines.insert(index, snigdhaos_core[0])
                                index += 1
                                del lines[index]
                                lines.insert(index, snigdhaos_core[1])
                                index += 1
                                del lines[index]
                                lines.insert(index, snigdhaos_core[2])
                            if snigdhaos_extra[0].replace("#", "") in line.strip():
                                snigdhaos_extra_found = True
                                index = lines.index(line)
                                del lines[index]
                                lines.insert(index, snigdhaos_extra[0])
                                index += 1
                                del lines[index]
                                lines.insert(index, snigdhaos_extra[1])
                                index += 1
                                del lines[index]
                                lines.insert(index, snigdhaos_extra[2])
                        if line.strip() == snigdhaos_core[0]:
                            snigdhaos_core_found = True
                        if line.strip() == snigdhaos_extra[0]:
                            snigdhaos_extra_found = True
                    if snigdhaos_core_found is False:
                        lines.append("\n")
                        for snigdhaos_core_line in snigdhaos_core:
                            lines.append(snigdhaos_core_line)
                    if snigdhaos_extra_found is False:
                        lines.append("\n")
                        for snigdhaos_extra_found_line in snigdhaos_extra_found:
                            lines.append(snigdhaos_extra_found_line)
                    logger.info("[Add Snigdha OS repos] Writing to %s" % pacman_conf)
                    if len(lines) > 0:
                        with open(pacman_conf, "w", encoding="utf-8") as w:
                            for l in lines:
                                w.write(l.strip() + "\n")
                            w.flush()
                        return 0
                    else:
                        logger.error("Failed to process %s" % pacman_conf)
                else:
                    logger.error("Failed to read %s" % pacman_conf)
        else:
            logger.info("Snigdha OS repos already setup inside pacman conf file")
            return 0
    except Exception as e:
        logger.error("Exception in LOC1469: %s" % e)
        return e

def verify_snigdhaos_pacman_conf():
    try:
        lines = None
        snigdhaos_core_setup = False
        snigdhaos_extra_setup = False
        with open(pacman_conf, "r") as r:
            lines = r.readlines()
        if lines is not None:
            for line in lines:
                if snigdhaos_core[0] in line.strip():
                    if "#" not in line.strip():
                        snigdhaos_core_setup = True
                    else:
                        return False

                if snigdhaos_extra[0] in line.strip():
                    if "#" not in line.strip():
                        snigdhaos_extra_setup = True
                    else:
                        return False
            if (
                snigdhaos_core_setup is True
                and snigdhaos_extra_setup is True
            ):
                return True
            else:
                return False
    except Exception as e:
        logger.error("Exception in LOC1604: %s" % e)

def update_textview_pacmanlog(self):
    lines = self.pacmanlog_queue.get()
    try:
        buffer = self.textbuffer_pacmanlog
        if len(lines) > 0:
            # DOCS : https://askubuntu.com/questions/435629/how-to-get-text-buffer-from-file-and-loading-into-textview-using-python-and-gtk
            end_iter = buffer.get_end_iter()
            for line in lines:
                if len(line) > 0:
                    buffer.insert(
                        end_iter,
                        line.decode("UTF-8"),
                        len(line),
                    )
    except Exception as e:
        logger.error(
            "Found Exception in LOC1628: %s" % e
        )
    finally:
        # DOCS : https://stackoverflow.com/questions/49637086/python-what-is-queue-task-done-used-for
        self.pacmanlog_queue.task_done()

def search(self, term):
    try:
        logger.info('Searching: "%s"' % term)
        pkg_matches = []
        category_dict = {}
        whitespace = False
        if term.strip():
            whitespace = True
        for pkg_list in self.packages.values():
            for pkg in pkg_list:
                if whitespace:
                    for te in term.split(" "):
                        if(
                            te.lower() in pkg.name.lower() or te.lower() in pkg.description.lower()
                        ):
                            if pkg not in pkg_matches:
                                pkg_matches.append(
                                    pkg,
                                )
                else:
                    if (
                        te.lower() in pkg.name.lower() or te.lower() in pkg.description.lower()
                    ):
                        pkg_matches.append(
                            pkg,
                        )
        
        category_name = None
        packages_cat = []
        for pkg_match in pkg_matches:
            if category_name == pkg_match.category:
                packages_cat.append(pkg_match)
                category_dict[category_name] = packages_cat
            elif category_name is None:
                packages_cat.append(pkg_match)
            else:
                packages_cat = []
                packages_cat.append(pkg_match)
                category_dict[pkg_match.category] = packages_cat
            category_name = pkg_match.category
        sorted_dict = None
        if len(category_dict) > 0:
            sorted_dict = dict(sorted(category_dict.items()))
            self.search_queue.put(
                sorted_dict,
            )
        else:
            self.search_queue.put(
                None,
            )
    except Exception as e:
        logger.error(
            "Found Exception in LOC1650: %s" % e 
        )

def remove_snigdhaos_repos():
    try:
        if verify_snigdhaos_pacman_conf() is True:
            if os.path.exists(pacman_conf):
                shutil.copy(
                    pacman_conf,
                    pacman_conf_backup,
                )
                logger.info(
                    "Reading From: %s" % pacman_conf
                )
                lines = []
                with open(
                    pacman_conf, "r", encoding="UTF-8"
                ) as r:
                    lines = r.readlines()
                if len(lines) > 0:
                    index = 0
                    for line in lines:
                        if "%s\n" % snigdhaos_core[0] == line:
                            index = line.index("%s\n" % snigdhaos_core[0])
                            if index > 0:
                                if distr != "snigdhaos":
                                    del lines[index]
                                    del lines[index]
                                    del lines[index]
                                else:
                                    lines[index] = "#%s\n" % snigdhaos_core[0]
                                    lines[index + 1] = "#%s\n" % snigdhaos_core[1]
                                    lines[index + 2] = "#%s\n" % snigdhaos_core[2]
                        elif (
                            "#" in line.strip()
                            and snigdhaos_core[0] == line.replace("#", "").strip()
                            and distr != "snigdhaos"
                        ):
                            index = lines.index(line)
                            del lines[index]
                            del lines[index]
                            del lines[index]
                        if "%s\n" %snigdhaos_extra[0] == line:
                            index = lines.index("%s\n" % snigdhaos_extra[0])
                            if index > 0:
                                if distr != "snigdhaos":
                                    del lines[index]
                                    del lines[index]
                                    del lines[index]
                                else:
                                    lines[index] = "#%s\n" % snigdhaos_extra[0]
                                    lines[index + 1] = "#%s\n" % snigdhaos_extra[1]
                                    lines[index + 2] = "#%s\n" % snigdhaos_extra[2]
                        elif (
                            "#" in line.strip()
                            and snigdhaos_extra[0] == line.replace("#", "").strip()
                            and distr != "snigdhaos"
                        ):
                            index = lines.index(line)
                            del lines[index]
                            del lines[index]
                            del lines[index]
                    if distr != "snigdhaos":
                        if lines[-1] == "\n":
                            del lines[-1]
                        if lines[-2] == "\n":
                            del lines[-2]
                        if lines[-3] == "\n":
                            del lines[-3]
                        if lines[-4] == "\n":
                            del lines[-4]
                    logger.info(
                        "[Remove Snigdha OS Repos] Writing to %s" % pacman_conf
                    )
                    if len(lines) > 0:
                        with open(pacman_conf, "w") as w:
                            w.writelines(lines)
                            w.flush() # DOCS : https://www.geeksforgeeks.org/file-flush-method-in-python/
                        return 0
                    else:
                        logger.error(
                            "Failed to process: %s" % pacman_conf
                        )
                else:
                    logger.error(
                        "Failed to read %s" % pacman_conf
                    )
        else:
            logger.info(
                "No Snigdha OS Repos inside Pacman Config!"
            )
            return 0
    except Exception as e:
        logger.error(
            "Found Exception in LOC1705: %s" % e
        )
        return e
def check_if_process_running(process_name):
    # DOCS : https://psutil.readthedocs.io/en/latest/#psutil.process_iter
    for proc in psutil.process_iter():
        try:
            pinfo = proc.as_dict(attrs=["pid", "name", "create_time"])
            if process_name == pinfo["pid"]:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def terminate_pacman():
    try:
        process_found = False
        for proc in psutil.process_iter():
            try:
                pinfo = proc.as_dict(attrs=["pid", "name", "create_time"])
                if pinfo["name"] == "pacman":
                    process_found = True
                    logger.debug(
                        "Killing Pacman Process: %s" %pinfo["name"]
                    )
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if process_found == True:
            if check_pacman_lockfile():
                os.unlink(pacman_lockfile)
    except Exception as e:
        logger.error(
            "Found Exception in LOC1810: %s" % e 
        )

def check_pacman_lockfile():
    try:
        if os.path.exists(pacman_lockfile):
            return True
        else:
            return False
    except Exception as e:
        logger.error(
            "Found Exception in LOC1832: %s" % e
        )

def is_thread_alive(thread_name):
    for thread in threading.enumerate():
        if thread.name == thread_name and thread.is_alive():
            return True
    return False

def print_running_threads():
    threads_alive = []
    for thread in threading.enumerate():
        if thread.is_alive():
            threads_alive.append(thread.name)
    for th in threads_alive:
        logger.debug(
            "Thread: %s Status: Alive" % th
        )

def check_holding_queue(self):
    while True:
        (
            package,
            action,
            widget,
            cmd_str,
            progress_dialog,
        ) = self.pkg_holding_queue.get()
        try:
            while check_pacman_lockfile() is True:
                time.sleep(0.2)
            th_subprocess = Thread(
                name = "thread_subprocess",
                target = start_subprocess,
                args=(
                    self,
                    cmd_str,
                    progress_dialog,
                    action,
                    package,
                    widget,
                ),
                daemon=True
            )
            th_subprocess.start()
        finally:
            self.pkg_holding_queue.task_done()

def get_pacman_process():
    try:
        for proc in psutil.process_iter():
            try:
                pinfo = proc.as_dict(attrs=["pid", "name", "create_time"])
                if pinfo["name"] == "pacman":
                    return " ".join(proc.cmdline)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.error(
            "Found Exception in LOC1888: %s" % e 
        )

def cache_btn():
    # fraction = 1 / len(packages)
    packages.sort()
    number = 1
    for pkg in packages:
        logger.debug(str(number) + "/" + str(len(packages)) + ": Caching " + pkg)
        cache(pkg, path_dir_cache)
        number = number + 1
        # progressbar.timeout_id = GLib.timeout_add(50, progressbar.update, fraction)

    logger.debug("Caching applications finished")

def restart_program():
    os.unlink("/tmp/blackbox.lock")
    python = sys.executable
    os.execl(python, python, *sys.argv)

def show_in_app_notification(self, message, err):
    if self.timeout_id is not None:
        GLib.source_remove(self.timeout_id)
        self.timeout_id = None

    if err is True:
        self.notification_label.set_markup(
            '<span background="yellow" foreground="black">' + message + "</span>"
        )
    else:
        self.notification_label.set_markup(
            '<span foreground="white">' + message + "</span>"
        )
    self.notification_revealer.set_reveal_child(True)
    self.timeout_id = GLib.timeout_add(3000, timeout, self)

def timeout(self):
    close_in_app_notification(self)


def close_in_app_notification(self):
    self.notification_revealer.set_reveal_child(False)
    GLib.source_remove(self.timeout_id)
    self.timeout_id = None

def update_package_import_textview(self, line):
    try:
        if len(line) > 0:
            self.msg_buffer.insert(
                self.msg_buffer.get_end_iter(),
                " %s" % line,
                len(" %s" % line),
            )
    except Exception as e:
        logger.error("[Exception] update_progress_textview(): %s" % e)
    finally:
        self.pkg_import_queue.task_done()
        text_mark_end = self.msg_buffer.create_mark(
            "end", self.msg_buffer.get_end_iter(), False
        )
        # scroll to the end of the textview
        self.textview.scroll_mark_onscreen(text_mark_end)

def monitor_package_import(self):
    while True:
        if self.stop_thread is True:
            break
        message = self.pkg_import_queue.get()
        GLib.idle_add(
            update_package_import_textview,
            self,
            message,
            priority=GLib.PRIORITY_DEFAULT,
        )

def update_package_status_label(label, text):
    label.set_markup(text)

def import_packages(self):
    try:
        packages_status_list = []
        package_failed = False
        package_err = {}
        count = 0
        if os.path.exists(pacman_cache_dir):
            query_pacman_clean_cache_str = [
                "pacman", 
                "-Sc", 
                "--noconfirm",
            ]
            logger.info(
                "Cleaning Pacman cache directory = %s" % pacman_cache_dir
            )
            event = "%s [INFO]: Cleaning pacman cache\n" % datetime.now().strftime(
                "%Y-%m-%d-%H-%M-%S"
            )
            self.pkg_import_queue.put(event)
            GLib.idle_add(
                update_package_status_label,
                self.label_package_status,
                "Status: <b>Cleaning pacman cache</b>",
            )
            process_pacman_cc = subprocess.Popen(
                query_pacman_clean_cache_str,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            out, err = process_pacman_cc.communicate(timeout=process_timeout)
            self.pkg_import_queue.put(out)
            if process_pacman_cc.returncode == 0:
                logger.info("Pacman cache directory cleaned")
            else:
                logger.error("Failed to clean Pacman cache directory")
            logger.info("Running full system upgrade")
            # run full system upgrade, Arch does not allow partial package updates
            query_str = ["pacman", "-Syu", "--noconfirm"]
            # query_str = ["pacman", "-Qqen"]
            logger.info("Running %s" % " ".join(query_str))
            event = "%s [INFO]:Running full system upgrade\n" % datetime.now().strftime(
                "%Y-%m-%d-%H-%M-%S"
            )
            self.pkg_import_queue.put(event)
            GLib.idle_add(
                update_package_status_label,
                self.label_package_status,
                "Status: <b>Performing full system upgrade - do not power off your system</b>",
            )
            output = []
            with subprocess.Popen(
                query_str,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True,
            ) as process:
                while True:
                    if process.poll() is not None:
                        break
                    for line in process.stdout:
                        # print(line.strip())
                        self.pkg_import_queue.put(line)
                        output.append(line)
                    # time.sleep(0.2)
            if process.returncode == 0:
                logger.info("Pacman system upgrade completed")
                GLib.idle_add(
                    update_package_status_label,
                    self.label_package_status,
                    "Status: <b> Full system upgrade - completed</b>",
                )
            else:
                if len(output) > 0:
                    if "there is nothing to do" not in output:
                        logger.error("Pacman system upgrade failed")
                        GLib.idle_add(
                            update_package_status_label,
                            self.label_package_status,
                            "Status: <b> Full system upgrade - failed</b>",
                        )
                        print("%s" % " ".join(output))
                        event = "%s [ERROR]: Installation of packages aborted due to errors\n" % datetime.now().strftime(
                            "%Y-%m-%d-%H-%M-%S"
                        )
                        self.pkg_import_queue.put(event)
                        logger.error("Installation of packages aborted due to errors")
                        return
                    # do not proceed with package installs if system upgrade fails
                    else:
                        return
            # iterate through list of packages, calling pacman -S on each one
            for package in self.packages_list:
                process_output = []
                package = package.strip()
                if len(package) > 0:
                    if "#" not in package:
                        query_str = ["pacman", "-S", package, "--needed", "--noconfirm"]
                        count += 1
                        logger.info("Running %s" % " ".join(query_str))
                        event = "%s [INFO]: Running %s\n" % (
                            datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
                            " ".join(query_str),
                        )
                        self.pkg_import_queue.put(event)
                        with subprocess.Popen(
                            query_str,
                            shell=False,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            bufsize=1,
                            universal_newlines=True,
                        ) as process:
                            while True:
                                if process.poll() is not None:
                                    break
                                for line in process.stdout:
                                    process_output.append(line.strip())
                                    self.pkg_import_queue.put(line)
                                # time.sleep(0.2)
                        if process.returncode == 0:
                            # since this is being run in another thread outside of main, use GLib to update UI component
                            GLib.idle_add(
                                update_package_status_label,
                                self.label_package_status,
                                "Status: <b>%s</b> -> <b>Installed</b>" % package,
                            )
                            GLib.idle_add(
                                update_package_status_label,
                                self.label_package_count,
                                "Progress: <b>%s/%s</b>"
                                % (count, len(self.packages_list)),
                            )
                            packages_status_list.append("%s -> Installed" % package)
                        else:
                            logger.error("%s --> Install failed" % package)
                            GLib.idle_add(
                                update_package_status_label,
                                self.label_package_status,
                                "Status: <b>%s</b> -> <b>Install failed</b>" % package,
                            )
                            GLib.idle_add(
                                update_package_status_label,
                                self.label_package_count,
                                "Progress: <b>%s/%s</b>"
                                % (count, len(self.packages_list)),
                            )
                            if len(process_output) > 0:
                                if "there is nothing to do" not in process_output:
                                    logger.error("%s" % " ".join(process_output))
                                    # store package error in dict
                                    package_err[package] = " ".join(process_output)
                            package_failed = True
                            packages_status_list.append("%s -> Failed" % package)
            if len(packages_status_list) > 0:
                self.pkg_status_queue.put(packages_status_list)
            if package_failed is True:
                GLib.idle_add(
                    update_package_status_label,
                    self.label_package_status,
                    "<b>Some packages have failed to install see %s</b>" % self.logfile,
                )
            # end
            event = "%s [INFO]: Completed, check the logfile for any errors\n" % (
                datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
            )
            self.pkg_import_queue.put(event)
    except Exception as e:
        logger.error("Exception in import_packages(): %s" % e)
    finally:
        self.pkg_err_queue.put(package_err)

def log_package_status(self):
    logger.info("Logging package status")
    packages_status_list = None
    package_err = None
    while True:
        try:
            time.sleep(0.2)
            packages_status_list = self.pkg_status_queue.get()
            package_err = self.pkg_err_queue.get()
        finally:
            self.pkg_status_queue.task_done()
            self.pkg_err_queue.task_done()
            with open(self.logfile, "w") as f:
                f.write(
                    "# This file was auto-generated by Sofirem on %s at %s\n"
                    % (
                        datetime.today().date(),
                        datetime.now().strftime("%H:%M:%S"),
                    ),
                )
                if packages_status_list is not None:
                    for package in packages_status_list:
                        if package.split("->")[0].strip() in package_err:
                            f.write("%s\n" % package)
                            f.write(
                                "\tERROR: %s\n"
                                % package_err[package.split("->")[0].strip()]
                            )
                        else:
                            f.write("%s\n" % package)
            break

def open_log_dir():
    try:
        subprocess.Popen(
            ["sudo", "-u", sudo_username, "xdg-open", log_dir],
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except Exception as e:
        logger.error("Exception in open_log_dir(): %s" % e)