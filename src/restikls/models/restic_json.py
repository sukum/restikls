# File: src/restikls/models/restic_json.py
"""
TypedDict definitions and runtime boundary validation functions for
JSON payloads returned by the Restic CLI.
"""

from typing import Any, TypedDict, cast

from ..lib.exceptions import ResticValidationError


# ==============================================================================
# TypedDict Definitions
# ==============================================================================


class SnapshotSummary(TypedDict, total=False):
    backup_start: str
    backup_end: str
    files_new: int
    files_changed: int
    files_unmodified: int
    dirs_new: int
    dirs_changed: int
    dirs_unmodified: int
    data_blobs: int
    tree_blobs: int
    data_added: int
    total_files_processed: int
    total_bytes_processed: int


class _SnapshotRequired(TypedDict):
    id: str
    short_id: str
    time: str
    paths: list[str]
    hostname: str
    username: str


class SnapshotPayload(_SnapshotRequired, total=False):
    tags: list[str]
    tree: str
    parent: str | None
    program_version: str
    summary: dict[str, Any]


class _SnapshotHeaderRequired(TypedDict):
    id: str
    time: str
    paths: list[str]


class SnapshotHeaderPayload(_SnapshotHeaderRequired, total=False):
    hostname: str
    username: str
    short_id: str
    tree: str


class _CommonNodeRequired(TypedDict):
    path: str
    name: str
    type: str
    mtime: str


class _CommonNodeOptional(TypedDict, total=False):
    mode: int
    permissions: str
    user: str
    group: str
    uid: int
    gid: int
    atime: str
    ctime: str
    struct_type: str
    message_type: str


class _FileNodeRequired(_CommonNodeRequired):
    size: int


class FileNodePayload(_FileNodeRequired, _CommonNodeOptional, total=False):
    pass


class DirNodePayload(_CommonNodeRequired, _CommonNodeOptional, total=False):
    pass


NodePayload = FileNodePayload | DirNodePayload


class _CommonFileMatchRequired(TypedDict):
    path: str
    type: str
    mtime: str


class _CommonFileMatchOptional(TypedDict, total=False):
    name: str
    mode: int
    permissions: str
    user: str
    group: str
    atime: str
    ctime: str


class _FileMatchRequired(_CommonFileMatchRequired):
    size: int


class FileMatchPayload(_FileMatchRequired, _CommonFileMatchOptional, total=False):
    pass

class DirMatchPayload(_CommonFileMatchRequired, _CommonFileMatchOptional, total=False):
    pass

FileMatchPayloadType = FileMatchPayload | DirMatchPayload


class _FileHistoryRequired(TypedDict):
    snapshot: str
    matches: list[FileMatchPayloadType]


class FileHistoryPayload(_FileHistoryRequired, total=False):
    hits: int


class _KeyRequired(TypedDict):
    id: str
    userName: str
    hostName: str
    created: str


class KeyPayload(_KeyRequired, total=False):
    current: bool


class _RepoStatsRequired(TypedDict):
    total_size: int
    total_blob_count: int


class RepoStatsPayload(_RepoStatsRequired, total=False):
    total_file_count: int
    total_uncompressed_size: int
    snapshots_count: int
    compression_ratio: float
    compression_progress: float
    compression_space_saving: float


class RepoCheckPayload(TypedDict, total=False):
    message: str


# ==============================================================================
# Validation Helpers
# ==============================================================================


def _require_dict(item: Any, context: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ResticValidationError(
            f"Expected {context} to be a JSON object, got {type(item).__name__}."
        )
    return item


def _require_field(
    d: dict[str, Any], field: str, expected_type: type | tuple[type, ...], context: str
) -> Any:
    if field not in d:
        raise ResticValidationError(f"Missing required field '{field}' in {context}.")
    val = d[field]
    if expected_type is int and isinstance(val, bool):
        raise ResticValidationError(
            f"Field '{field}' in {context} must be int, got bool."
        )
    if not isinstance(val, expected_type):
        type_name = (
            ", ".join(t.__name__ for t in expected_type)
            if isinstance(expected_type, tuple)
            else expected_type.__name__
        )
        raise ResticValidationError(
            f"Field '{field}' in {context} must be {type_name}, got {type(val).__name__}."
        )
    return val


def _require_list_of_strings(
    d: dict[str, Any], field: str, context: str, allow_none: bool = False
) -> list[str]:
    if field not in d:
        raise ResticValidationError(f"Missing required field '{field}' in {context}.")
    val = d[field]
    if val is None and allow_none:
        d[field] = []
        return d[field]
    if not isinstance(val, list):
        raise ResticValidationError(
            f"Field '{field}' in {context} must be list, got {type(val).__name__}."
        )
    for i, item in enumerate(val):
        if not isinstance(item, str):
            raise ResticValidationError(
                f"Item at index {i} in '{field}' in {context} must be str, got {type(item).__name__}."
            )
    return val


# ==============================================================================
# Boundary Parsers
# ==============================================================================


def parse_snapshot_item(item: Any, context: str = "snapshot") -> SnapshotPayload:
    """Validate a single snapshot payload dictionary."""
    d = _require_dict(item, context)
    _require_field(d, "id", str, context)
    _require_field(d, "short_id", str, context)
    _require_field(d, "time", str, context)
    _require_list_of_strings(d, "paths", context)
    _require_field(d, "hostname", str, context)
    _require_field(d, "username", str, context)
    if "tags" in d:
        _require_list_of_strings(d, "tags", context, allow_none=True)
    return cast(SnapshotPayload, d)


def parse_snapshots(raw: Any) -> list[SnapshotPayload]:
    """Validate a list of snapshots returned from 'restic snapshots --json'."""
    if not isinstance(raw, list):
        raise ResticValidationError(
            f"Expected snapshots output to be a JSON list, got {type(raw).__name__}."
        )
    for i, item in enumerate(raw):
        parse_snapshot_item(item, context=f"snapshot[{i}]")
    return cast(list[SnapshotPayload], raw)


def parse_snapshot(raw: Any) -> list[SnapshotPayload]:
    """Validate snapshots output for a specific snapshot lookup."""
    return parse_snapshots(raw)


def parse_snapshot_header(item: Any, context: str = "snapshot header") -> SnapshotHeaderPayload:
    """Validate line 0 of 'restic ls --json' representing snapshot root/header."""
    d = _require_dict(item, context)
    _require_field(d, "id", str, context)
    _require_field(d, "time", str, context)
    _require_list_of_strings(d, "paths", context)
    return cast(SnapshotHeaderPayload, d)


def parse_dir_node(item: Any, context: str = "dir node") -> DirNodePayload:
    """Validate a directory entry returned from 'restic ls --json'."""
    d = _require_dict(item, context)
    _require_field(d, "path", str, context)
    _require_field(d, "name", str, context)
    _require_field(d, "type", str, context)
    _require_field(d, "mtime", str, context)
    return cast(DirNodePayload, d)


def parse_file_node(item: Any, context: str = "file node") -> FileNodePayload:
    """Validate a file entry returned from 'restic ls --json'."""
    d = _require_dict(item, context)
    _require_field(d, "path", str, context)
    _require_field(d, "name", str, context)
    _require_field(d, "type", str, context)
    _require_field(d, "mtime", str, context)
    _require_field(d, "size", int, context)
    return cast(FileNodePayload, d)


def parse_node(item: Any, context: str = "node") -> NodePayload:
    """Validate a file/dir/node entry returned from 'restic ls --json'."""
    d = _require_dict(item, context)
    _require_field(d, "path", str, context)
    _require_field(d, "name", str, context)
    node_type = _require_field(d, "type", str, context)
    _require_field(d, "mtime", str, context)
    if node_type == "file":
        _require_field(d, "size", int, context)
        return cast(FileNodePayload, d)
    if "size" in d:
        _require_field(d, "size", int, context)
    if node_type == "dir":
        return cast(DirNodePayload, d)
    return cast(NodePayload, d)


def parse_snapshot_files_raw(raw: Any) -> list[dict[str, Any]]:
    """
    Validate the combined lines from 'restic ls --json'.
    Item 0 is the snapshot header, and items 1..N are file nodes.
    Returns the validated list to be cached and split by caller.
    """
    if not isinstance(raw, list) or len(raw) == 0:
        raise ResticValidationError(
            f"Expected snapshot files output to be a non-empty list, got {type(raw).__name__}."
        )
    parse_snapshot_header(raw[0], context="snapshot header (ls line 0)")
    for i, file_item in enumerate(raw[1:], start=1):
        parse_node(file_item, context=f"file node[{i}]")
    return raw


def parse_snapshot_files(raw: Any) -> tuple[SnapshotHeaderPayload, list[NodePayload]]:
    """
    Validate and return snapshot files as a (header, files) tuple.
    """
    validated_raw = parse_snapshot_files_raw(raw)
    header = cast(SnapshotHeaderPayload, validated_raw[0])
    files = cast(list[NodePayload], validated_raw[1:])
    return header, files


def parse_file_match(item: Any, context: str = "file match") -> FileMatchPayloadType:
    """Validate an individual match item within find output."""
    d = _require_dict(item, context)
    _require_field(d, "path", str, context)
    file_type = _require_field(d, "type", str, context)
    _require_field(d, "mtime", str, context)
    # _require_field(d, "size", int, context)
    # return cast(FileMatchPayloadType, d)
    if file_type == "file":
        _require_field(d, "size", int, context)
        return cast(FileMatchPayload, d)
    if "size" in d:
        _require_field(d, "size", int, context)
    if file_type == "dir":
        return cast(DirMatchPayload, d)
    return cast(FileMatchPayloadType, d)



def parse_file_history(raw: Any) -> list[FileHistoryPayload]:
    """Validate list of file history matches returned from 'restic find --json'."""
    if not isinstance(raw, list):
        raise ResticValidationError(
            f"Expected file history output to be a list, got {type(raw).__name__}."
        )
    for i, item in enumerate(raw):
        context = f"history[{i}]"
        d = _require_dict(item, context)
        _require_field(d, "snapshot", str, context)
        matches = _require_field(d, "matches", list, context)
        if len(matches) == 0:
            raise ResticValidationError(
                f"Field 'matches' in {context} must not be empty."
            )
        for j, match in enumerate(matches):
            parse_file_match(match, context=f"{context}.matches[{j}]")
    return cast(list[FileHistoryPayload], raw)


def parse_keys(raw: Any) -> list[KeyPayload]:
    """Validate list of keys returned from 'restic key list --json'."""
    if not isinstance(raw, list):
        raise ResticValidationError(
            f"Expected keys output to be a list, got {type(raw).__name__}."
        )
    for i, item in enumerate(raw):
        context = f"key[{i}]"
        d = _require_dict(item, context)
        _require_field(d, "id", str, context)
        _require_field(d, "userName", str, context)
        _require_field(d, "hostName", str, context)
        _require_field(d, "created", str, context)
    return cast(list[KeyPayload], raw)


def parse_key(raw: Any) -> KeyPayload:
    """Validate a single key payload."""
    d = _require_dict(raw, "key")
    _require_field(d, "id", str, "key")
    _require_field(d, "userName", str, "key")
    _require_field(d, "hostName", str, "key")
    _require_field(d, "created", str, "key")
    return cast(KeyPayload, d)


def parse_repo_stats(raw: Any) -> RepoStatsPayload:
    """Validate repository stats returned from 'restic stats --mode raw-data --json'."""
    d = _require_dict(raw, "repo stats")
    _require_field(d, "total_size", int, "repo stats")
    _require_field(d, "total_blob_count", int, "repo stats")
    return cast(RepoStatsPayload, d)


def parse_check(raw: Any) -> RepoCheckPayload:
    """Validate output returned from 'restic check --json'."""
    d = _require_dict(raw, "repo check")
    return cast(RepoCheckPayload, d)
