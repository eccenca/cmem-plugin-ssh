"""Retrieval class for SSH files"""

import re
import stat
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from cmem_plugin_base.dataintegration.context import ExecutionContext, ExecutionReport
from paramiko import SFTPAttributes, SSHClient


def context_report(context: ExecutionContext, files: list[Any]) -> None:
    """Report for user context"""
    if context is not None:
        context.report.update(
            ExecutionReport(
                entity_count=len(files), operation="wait", operation_desc="files listed"
            )
        )


class SSHRetrieval:
    """Retrieval class for listing files of an SSH instance"""

    def __init__(
        self,
        ssh_client: SSHClient,
        no_subfolder: bool,
        regex: str,
    ):
        self.ssh_client = ssh_client  # Use SSHClient instead of SFTPClient
        self.no_subfolder = no_subfolder
        self.regex = regex
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.sftp_pool = threading.local()  # Thread-local SFTP client

    def get_sftp(self) -> Any:  # noqa: ANN401
        """Generate thread-local SFTP-client access"""
        if not hasattr(self.sftp_pool, "client"):
            self.sftp_pool.client = self.ssh_client.open_sftp()
        return self.sftp_pool.client

    # for now, ignore that it is too complex, need to change after finalizing download
    def list_files_parallel(  # noqa: PLR0913, C901
        self,
        path: str,
        files: list[SFTPAttributes],
        context: ExecutionContext | None,
        depth: int = -1,
        curr_depth: int = 0,
        no_of_max_hits: int = -1,
        workers: int = 32,
        download_files: bool = False,
        download_path: Path = Path(),
    ) -> list[SFTPAttributes]:
        """List all files recursively with concurrency. Can also download when the flag is set."""
        if curr_depth == 0:
            self.stop_event.clear()

        self.cancel_listdir(context)
        if self.stop_event.is_set() or (depth != -1 and curr_depth >= depth):
            return files

        subdirectories: list[str] = []
        items = self._get_folder_items(path)

        for item in items:
            self.cancel_listdir(context)
            if self.stop_event.is_set():
                return files

            added = self.add_node(files, item, no_of_max_hits)

            if added and download_files:
                full_path = f"{path.rstrip('/')}/{item.filename}"
                self.get_sftp().get(remotepath=full_path, localpath=download_path / item.filename)

            context_report(context, files)

            if added and self.check_stop(files, no_of_max_hits):
                return files

            item_mode = item.st_mode
            if item_mode and stat.S_ISDIR(item_mode) and not self.no_subfolder:
                full_path = f"{path.rstrip('/')}/{item.filename}"
                subdirectories.append(full_path)

        if subdirectories and not self.stop_event.is_set():
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [
                    executor.submit(
                        self.list_files_parallel,
                        sd,
                        files,
                        None,
                        depth,
                        curr_depth + 1,
                        no_of_max_hits,
                        workers,
                    )
                    for sd in subdirectories
                ]
                for fut in as_completed(futures):
                    self.cancel_listdir(context)
                    if self.stop_event.is_set():
                        break
                    fut.result()
                    context_report(context, files)

        return files

    def check_stop(self, files: list[Any], max_results: int) -> bool:
        """Check whether max_results reached and stop if so"""
        with self.lock:
            if max_results != -1 and len(files) >= max_results:
                self.stop_event.set()
                return True
        return False

    def cancel_listdir(self, context: ExecutionContext) -> None:
        """Cancel listdir if workflow is cancelled"""
        try:
            if context.workflow.status() == "Canceling":
                self.stop_event.set()
        except AttributeError:
            pass

    def add_node(
        self, files: list[SFTPAttributes], item: SFTPAttributes, no_of_max_hits: int
    ) -> bool:
        """Add file or folder node to result"""
        with self.lock:
            if no_of_max_hits != -1 and len(files) >= no_of_max_hits:
                self.stop_event.set()
                return False

            mode = item.st_mode
            if mode and re.fullmatch(self.regex, item.filename) and not stat.S_ISDIR(mode):
                files.append(item)
                if no_of_max_hits != -1 and len(files) >= no_of_max_hits:
                    self.stop_event.set()
                return True

        return False

    def _get_folder_items(self, path: str) -> Any:  # noqa: ANN401
        return self.get_sftp().listdir_attr(path if path else ".")
