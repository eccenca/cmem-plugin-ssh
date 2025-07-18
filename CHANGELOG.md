# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/) and this project adheres to [Semantic Versioning](https://semver.org/)

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

