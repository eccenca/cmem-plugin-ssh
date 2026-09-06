<!-- markdownlint-disable MD012 MD013 MD024 MD033 -->
# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/) and this project adheres to [Semantic Versioning](https://semver.org/)

## [2.0.1] 2026-09-06

### Changed

- updated dependencies and template
- rewrote the task documentation, parameter descriptions and dropdown labels of all four
  tasks: they now describe what the tasks actually do, including the file name collisions
  on download and upload, the unpacking of gzip content on upload, the ignored exit code
  on command execution, and the fact that host keys are accepted without verification

### Fixed

- the plugin no longer offers the SSH agent keys and `~/.ssh` private keys of the Corporate Memory host to the remote server; only the credentials configured on the task are used

## [2.0.0] 2026-08-10

### Changed

- update template
- update paramiko dependency to 5.x (CVE-2026-44405)

### Removed

- DSS/DSA key support (paramiko 5.x completely removed DSS/DSA key support)


## [1.1.1] 2025-12-03

### Fixed

- autocompletion for folders works now for case-sensitive folders (example: test and TEst)


## [1.1.0] 2025-10-20

### Fixed

- move connection test from init to execute phase (all tasks)
  - this avoids project loading errors
- Fix typos and grammar in parameter descriptions

### Added

- testing infrastructure based in testcontainers

### Changed

- update template and ensure python 3.13 compatability

## [1.0.0] 2025-07-18

### Changed

- Use `tempfile` to create a temporary directory for downloads.
- Added support for detecting and decompressing Gzip files during upload.
- Improved file type detection (text vs. binary) for uploads.

## [0.6.0] 2025-07-03

### Added

- Execute commands Plugin
  - Execute a given command on a given SSH instance
  - allow for File input or not input
  - Can create output files or just structured output


## [0.5.0] 2025-07-01

### Added

- List Plugin
  - List files from a given SSH instance
- Download Plugin
  - Download files from a given SSH instance
- Upload Plugin
  - Upload files from a given SSH instance

