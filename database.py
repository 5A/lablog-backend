# -*- coding: utf-8 -*-

"""database.py:
This module defines how lablog manages database storage and backup.
You can modify from here if not using local disk as storage.
"""

__author__ = "Zhi Zi"
__email__ = "x@zzi.io"
__version__ = "20240526"

# std libs
import os
import logging
import json
import asyncio
import time
# this package
from .server_config import DatabaseConfig
from .lablog import Lablog

lg = logging.getLogger(__name__)


class LablogDatabaseManager():
    def __init__(self, lablog: Lablog, database_config: DatabaseConfig) -> None:
        self.lablog = lablog
        self.cfg = database_config
        # this hash information is used to compare if the data on disk is
        # the same as the one in memory, to see if it has been changed.
        self.data_hash: str = ""
        self.manager_running = False
        self.eloop = asyncio.get_event_loop()

    def start_scheduler(self):
        self.manager_running = True
        self.eloop.create_task(self.periodic_check())

    def stop_scheduler(self):
        self.manager_running = False

    async def periodic_check(self):
        """
        Checks local file changes, load changes into memory, and save database periodically.
        NOTE that this function eventually calls methods that modifies data of lablog
        and data on the disk, be aware of data conflicts and data corruption.
        This is the asynchronous version, thus no mutex is needed.
        """
        t_next_autosave = time.time() + 3600
        while self.manager_running:
            # [TODO]: check local files for auto loading
            # ...
            if time.time() > t_next_autosave:
                # Save database files every hour (set check_hash=True to save changes only)
                self.save_database(check_hash=True)
                t_next_autosave = t_next_autosave + 3600
            # release control and come back to check every second
            await asyncio.sleep(1)

    def load_database(self):
        root_path = self.cfg.root_path
        db_path = root_path + "blogdata.json"
        if os.path.exists(db_path):
            lg.info("Database files found, loading posts and comments data.")
            self.lablog.load_from_file(db_path)
        else:
            lg.warning("No database file found!")
            lg.warning(
                "If this is a new installation of lablog, this warning can be safely ignored.")
            lg.warning("Creating new database and saving it.")
            self.save_database()

    def save_database(self, check_hash: bool = False):
        if check_hash:
            new_hash = self.lablog.get_data_hash()
            if new_hash == self.data_hash:
                lg.debug(
                    "Skipped saving database file because hash matches saved version.")
                return
        root_path = self.cfg.root_path
        db_path = root_path + "blogdata.json"
        if os.path.exists(db_path):
            lg.info("Overwriting database file.")
        else:
            lg.warning("Saving database as new file at {}".format(
                db_path))
        # write to disk and save hash of current saved version
        self.lablog.serialize_to_file(db_path)
        self.data_hash = self.lablog.get_data_hash()
