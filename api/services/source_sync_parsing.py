from __future__ import annotations

import csv
import hashlib
import io
import math
import posixpath
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

from api.services.source_sync_contracts import ParsedSourceRow, SourceSyncError
from api.services.source_sync_identity import (
    clean_text,
    limited_text,
    normalize_title,
    normalized_directors,
)


@dataclass(frozen=True)
class ParseLimits:
    max_source_bytes: int = 5 * 1024 * 1024
    max_source_rows: int = 5000
    max_source_columns: int = 64
    max_csv_rows: int = 5025
    max_cell_chars: int = 8192
    max_numeric_chars: int = 64
    max_xlsx_members: int = 128
    max_xlsx_uncompressed_bytes: int = 20 * 1024 * 1024
    max_xlsx_member_bytes: int = 8 * 1024 * 1024
    max_xlsx_compression_ratio: int = 100
    max_xlsx_shared_strings: int = 100_000
    max_xlsx_shared_string_bytes: int = 5 * 1024 * 1024
    max_xlsx_rows: int = 5025
    max_xlsx_cells: int = 5025 * 64


DEFAULT_PARSE_LIMITS = ParseLimits()

REQUIRED_FIELDS = ("title", "time", "director", "year")
FIELD_ALIASES = {
    "title": ("Title", "Name", "Movie", "Movie Title", "Film", "Film Title"),
    "time": (
        "Time",
        "Total Time",
        "Runtime",
        "Run Time",
        "Duration",
        "Minutes",
        "Runtime Min",
    ),
    "director": ("Director", "Directors", "Director(s)", "Artist"),
    "year": ("Year", "Release Year", "Movie Year"),
    "genre": ("Genre", "Genres"),
    "content_rating": ("Content Rating", "Rating", "Rated", "Certificate"),
    "release_date": ("Release Date", "Released", "Date"),
    "hd": ("HD", "High Definition", "Quality"),
}

_SPACE_RE = re.compile(r"\s+")
_ASCII_INTEGER_RE = re.compile(r"[0-9]+", re.ASCII)
_ASCII_DECIMAL_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?", re.ASCII)
_XLSX_CELL_REF_RE = re.compile(r"([A-Z]{1,3})([1-9][0-9]*)", re.ASCII)


def _bounded_invalid_value(label: str, text: str, *, limits: ParseLimits) -> SourceSyncError:
    if len(text) <= limits.max_numeric_chars:
        return SourceSyncError(f"Invalid {label} '{text}'")
    return SourceSyncError(f"Invalid {label} value")


def _rounded_number(text: str) -> int:
    number = float(text)
    if not math.isfinite(number):
        raise ValueError("number must be finite")
    return round(number)


def _parse_clock_runtime(text: str, *, limits: ParseLimits) -> int:
    parts = text.split(":")
    if len(parts) not in {2, 3} or not all(_ASCII_DECIMAL_RE.fullmatch(part) for part in parts):
        raise _bounded_invalid_value("runtime", text, limits=limits)
    numbers = [float(part) for part in parts]
    if not all(math.isfinite(number) for number in numbers):
        raise ValueError("number must be finite")
    if len(numbers) == 3:
        hours, minutes, seconds = numbers
    else:
        hours = 0
        minutes, seconds = numbers
    return round(hours * 60 + minutes + seconds / 60)


def _parse_runtime_text(text: str, *, limits: ParseLimits) -> int:
    lowered = text.casefold()
    decimal = r"[0-9]+(?:\.[0-9]+)?"
    minute_match = re.fullmatch(rf"({decimal})\s*(?:m|min|mins|minute|minutes)", lowered, re.ASCII)
    if minute_match:
        return _rounded_number(minute_match.group(1))
    hour_minute_match = re.fullmatch(
        rf"(?:({decimal})\s*h(?:ours?)?)?\s*" rf"(?:({decimal})\s*m(?:in(?:ute)?s?)?)?",
        lowered,
        re.ASCII,
    )
    if hour_minute_match and any(hour_minute_match.groups()):
        hours = float(hour_minute_match.group(1) or 0)
        minutes = float(hour_minute_match.group(2) or 0)
        if not math.isfinite(hours) or not math.isfinite(minutes):
            raise ValueError("number must be finite")
        return round(hours * 60 + minutes)
    if _ASCII_INTEGER_RE.fullmatch(text):
        return int(text)
    return _parse_clock_runtime(text, limits=limits)


def parse_runtime(
    value: object,
    *,
    limits: ParseLimits = DEFAULT_PARSE_LIMITS,
) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    if len(text) > limits.max_numeric_chars:
        raise _bounded_invalid_value("runtime", text, limits=limits)

    try:
        runtime = _parse_runtime_text(text, limits=limits)
    except SourceSyncError:
        raise
    except (OverflowError, ValueError) as exc:
        raise _bounded_invalid_value("runtime", text, limits=limits) from exc

    if runtime <= 0 or runtime > 1000:
        raise SourceSyncError(f"Runtime '{text}' is outside the accepted range")
    return runtime


def parse_year(
    value: object,
    *,
    limits: ParseLimits = DEFAULT_PARSE_LIMITS,
) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    if len(text) > limits.max_numeric_chars:
        raise _bounded_invalid_value("year", text, limits=limits)
    if re.fullmatch(r"[0-9]+\.0+", text, re.ASCII):
        text = text.split(".", 1)[0]
    if not _ASCII_INTEGER_RE.fullmatch(text):
        raise _bounded_invalid_value("year", text, limits=limits)
    try:
        year = int(text)
    except ValueError as exc:
        raise _bounded_invalid_value("year", text, limits=limits) from exc
    if year < 1888 or year > 2100:
        raise SourceSyncError(f"Year '{text}' is outside the accepted range")
    return year


def parse_hd(
    value: object,
    *,
    limits: ParseLimits = DEFAULT_PARSE_LIMITS,
) -> bool | None:
    text = clean_text(value)
    if text is None:
        return None
    if len(text) > limits.max_numeric_chars:
        raise SourceSyncError("Invalid HD value")
    lowered = text.casefold()
    if lowered in {"1", "true", "yes", "y", "hd"}:
        return True
    if lowered in {"0", "false", "no", "n", "sd"}:
        return False
    raise SourceSyncError(f"Invalid HD value '{text}'")


def _header_key(value: object) -> str:
    text = str(value or "").replace("\ufeff", "").casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return _SPACE_RE.sub(" ", text).strip()


def _find_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    aliases_by_field = {
        field: frozenset(_header_key(alias) for alias in aliases)
        for field, aliases in FIELD_ALIASES.items()
    }
    for index, row in enumerate(rows):
        positions_by_name: dict[str, list[int]] = {}
        for position, value in enumerate(row):
            name = _header_key(value)
            if name:
                positions_by_name.setdefault(name, []).append(position)

        candidates: dict[str, list[int]] = {
            field: sorted(
                position for alias in aliases for position in positions_by_name.get(alias, ())
            )
            for field, aliases in aliases_by_field.items()
        }
        if not all(candidates[field] for field in REQUIRED_FIELDS):
            continue
        ambiguous = [field for field, positions in candidates.items() if len(positions) > 1]
        if ambiguous:
            labels = ", ".join(field.replace("_", " ") for field in ambiguous)
            raise SourceSyncError(f"Upload contains ambiguous columns for: {labels}")
        return index, {field: positions[0] for field, positions in candidates.items() if positions}
    raise SourceSyncError(
        "Upload must contain title, runtime, director, and year columns. "
        "Common headers such as Name, Movie Title, Total Time, Runtime, Artist, "
        "Director, Release Year, and Year are accepted."
    )


def _parse_source_rows(
    raw_rows: list[list[str]],
    *,
    limits: ParseLimits = DEFAULT_PARSE_LIMITS,
) -> list[ParsedSourceRow]:
    header_index, columns = _find_header(raw_rows)
    data_rows = [row for row in raw_rows[header_index + 1 :] if any(cell.strip() for cell in row)]
    if not data_rows:
        raise SourceSyncError("The upload contains no movie rows")
    if len(data_rows) > limits.max_source_rows:
        raise SourceSyncError(f"The upload contains more than {limits.max_source_rows} rows")

    duplicate_keys: list[str] = []
    provisional: list[dict[str, object]] = []
    for offset, row in enumerate(data_rows, start=header_index + 2):

        def field_value(field: str) -> str:
            column = columns.get(field)
            if column is None or column >= len(row):
                return ""
            return row[column].strip()

        title = limited_text(
            field_value("title"),
            field_name="title",
            max_length=300,
            row_number=offset,
        )
        if title is None:
            raise SourceSyncError(f"Row {offset} has no title")
        runtime = parse_runtime(field_value("time"), limits=limits)
        year = parse_year(field_value("year"), limits=limits)
        director = limited_text(
            field_value("director"),
            field_name="director",
            max_length=500,
            row_number=offset,
        )
        directors = normalized_directors(director)
        raw_data = {
            label: field_value(field)
            for field, label in (
                ("title", "Title"),
                ("time", "Time"),
                ("director", "Director"),
                ("year", "Year"),
                ("genre", "Genre"),
                ("content_rating", "Content Rating"),
                ("release_date", "Release Date"),
                ("hd", "HD"),
            )
        }
        duplicate_key = hashlib.sha256(
            "\x1f".join(
                [
                    normalize_title(title),
                    str(year or ""),
                    str(runtime or ""),
                    "|".join(directors),
                ]
            ).encode("utf-8")
        ).hexdigest()
        duplicate_keys.append(duplicate_key)
        provisional.append(
            {
                "row_number": offset,
                "title": title,
                "normalized_title": normalize_title(title),
                "runtime": runtime,
                "director": director,
                "normalized_directors": directors,
                "year": year,
                "genre": limited_text(
                    field_value("genre"),
                    field_name="genre",
                    max_length=200,
                    row_number=offset,
                ),
                "content_rating": limited_text(
                    field_value("content_rating"),
                    field_name="content rating",
                    max_length=100,
                    row_number=offset,
                ),
                "release_date": limited_text(
                    field_value("release_date"),
                    field_name="release date",
                    max_length=80,
                    row_number=offset,
                ),
                "hd": parse_hd(field_value("hd"), limits=limits),
                "raw_data": raw_data,
                "duplicate_key": duplicate_key,
            }
        )

    duplicate_counts = Counter(duplicate_keys)
    return [
        ParsedSourceRow(
            row_number=int(row["row_number"]),
            title=str(row["title"]),
            normalized_title=str(row["normalized_title"]),
            runtime=row["runtime"],
            director=row["director"],
            normalized_directors=row["normalized_directors"],
            year=row["year"],
            genre=row["genre"],
            content_rating=row["content_rating"],
            release_date=row["release_date"],
            hd=row["hd"],
            duplicate_group=(
                str(row["duplicate_key"])
                if duplicate_counts[str(row["duplicate_key"])] > 1
                else None
            ),
            raw_data=row["raw_data"],
        )
        for row in provisional
    ]


def _read_csv_rows(text: str, *, limits: ParseLimits) -> list[list[str]]:
    rows: list[list[str]] = []
    try:
        for row in csv.reader(io.StringIO(text)):
            if len(rows) >= limits.max_csv_rows:
                raise SourceSyncError(
                    f"The upload contains more than {limits.max_source_rows} rows"
                )
            if len(row) > limits.max_source_columns:
                raise SourceSyncError("The uploaded CSV contains too many columns")
            if any(len(cell) > limits.max_cell_chars for cell in row):
                raise SourceSyncError("The uploaded CSV contains a cell that is too large")
            rows.append(row)
    except csv.Error as exc:
        raise SourceSyncError(f"CSV parsing failed: {exc}") from exc
    return rows


def parse_source_csv(
    content: bytes,
    *,
    limits: ParseLimits = DEFAULT_PARSE_LIMITS,
) -> tuple[str, list[ParsedSourceRow]]:
    if not content:
        raise SourceSyncError("The uploaded CSV is empty")
    if len(content) > limits.max_source_bytes:
        raise SourceSyncError("The uploaded CSV is larger than 5 MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceSyncError("The CSV must use UTF-8 encoding") from exc
    rows = _read_csv_rows(text, limits=limits)
    return text, _parse_source_rows(rows, limits=limits)


def _xlsx_column_index(cell_ref: str, *, limits: ParseLimits) -> int:
    match = _XLSX_CELL_REF_RE.fullmatch(cell_ref)
    if match is None:
        raise SourceSyncError("XLSX cell reference is invalid")
    index = 0
    for char in match.group(1):
        index = index * 26 + (ord(char) - ord("A") + 1)
    index -= 1
    if index >= limits.max_source_columns:
        raise SourceSyncError("The XLSX file contains too many columns")
    return index


def _xlsx_text(element: ElementTree.Element) -> str:
    return "".join(element.itertext())


def _xlsx_member_info(workbook: zipfile.ZipFile, name: str) -> zipfile.ZipInfo:
    try:
        return workbook.getinfo(name)
    except KeyError as exc:
        raise SourceSyncError(f"XLSX member {name} is missing") from exc


def _validate_xlsx_member(info: zipfile.ZipInfo, *, limits: ParseLimits) -> None:
    if info.file_size > limits.max_xlsx_member_bytes:
        raise SourceSyncError("The XLSX file expands beyond the supported import size")
    if (
        info.compress_size > 0
        and info.file_size / info.compress_size > limits.max_xlsx_compression_ratio
    ):
        raise SourceSyncError("The XLSX file compression ratio is too high")


def _validate_xlsx_archive(workbook: zipfile.ZipFile, *, limits: ParseLimits) -> None:
    members = workbook.infolist()
    if len(members) > limits.max_xlsx_members:
        raise SourceSyncError("The XLSX file contains too many parts")
    total_uncompressed = 0
    for info in members:
        _validate_xlsx_member(info, limits=limits)
        total_uncompressed += info.file_size
        if total_uncompressed > limits.max_xlsx_uncompressed_bytes:
            raise SourceSyncError("The XLSX file expands beyond the supported import size")


def _xlsx_read_xml(
    workbook: zipfile.ZipFile,
    name: str,
    error_message: str,
    *,
    limits: ParseLimits,
) -> ElementTree.Element:
    info = _xlsx_member_info(workbook, name)
    _validate_xlsx_member(info, limits=limits)
    try:
        return ElementTree.fromstring(workbook.read(info))
    except ElementTree.ParseError as exc:
        raise SourceSyncError(error_message) from exc


def _xlsx_shared_strings(
    workbook: zipfile.ZipFile,
    *,
    limits: ParseLimits,
) -> list[str]:
    try:
        info = workbook.getinfo("xl/sharedStrings.xml")
    except KeyError:
        return []
    _validate_xlsx_member(info, limits=limits)

    shared_strings: list[str] = []
    total_text_bytes = 0
    try:
        with workbook.open(info) as member:
            for _event, element in ElementTree.iterparse(member, events=("end",)):
                if element.tag.rsplit("}", 1)[-1] != "si":
                    continue
                if len(shared_strings) >= limits.max_xlsx_shared_strings:
                    raise SourceSyncError("The XLSX file contains too many shared strings")
                text = _xlsx_text(element)
                total_text_bytes += len(text.encode("utf-8"))
                if total_text_bytes > limits.max_xlsx_shared_string_bytes:
                    raise SourceSyncError("The XLSX shared strings are too large")
                if len(text) > limits.max_cell_chars:
                    raise SourceSyncError("The XLSX file contains a cell that is too large")
                shared_strings.append(text)
                element.clear()
    except ElementTree.ParseError as exc:
        raise SourceSyncError("XLSX shared strings could not be read") from exc
    return shared_strings


def _resolve_xlsx_relationship_target(relationship: ElementTree.Element) -> str:
    target_mode = relationship.attrib.get("TargetMode", "Internal")
    target = relationship.attrib.get("Target", "")
    try:
        parsed = urlsplit(target)
    except ValueError as exc:
        raise SourceSyncError("XLSX first worksheet could not be resolved") from exc
    decoded_path = unquote(parsed.path)
    invalid_uri = bool(parsed.scheme or parsed.netloc or parsed.query or parsed.fragment)
    path_parts = decoded_path.split("/")
    if (
        target_mode.casefold() != "internal"
        or not target
        or invalid_uri
        or "\\" in decoded_path
        or ".." in path_parts
    ):
        raise SourceSyncError("XLSX first worksheet could not be resolved")

    if decoded_path.startswith("/"):
        resolved = posixpath.normpath(decoded_path.lstrip("/"))
    else:
        resolved = posixpath.normpath(posixpath.join("xl", decoded_path))
    if not resolved.startswith("xl/"):
        raise SourceSyncError("XLSX first worksheet could not be resolved")
    return resolved


def _xlsx_first_sheet_path(workbook: zipfile.ZipFile, *, limits: ParseLimits) -> str:
    workbook_root = _xlsx_read_xml(
        workbook,
        "xl/workbook.xml",
        "XLSX workbook metadata could not be read",
        limits=limits,
    )
    rels_root = _xlsx_read_xml(
        workbook,
        "xl/_rels/workbook.xml.rels",
        "XLSX workbook metadata could not be read",
        limits=limits,
    )

    first_sheet = workbook_root.find(".//{*}sheet")
    relationship_id = (
        first_sheet.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        if first_sheet is not None
        else None
    )
    if relationship_id is None:
        raise SourceSyncError("XLSX workbook has no worksheets")

    for relationship in rels_root.findall(".//{*}Relationship"):
        if relationship.attrib.get("Id") == relationship_id:
            return _resolve_xlsx_relationship_target(relationship)
    raise SourceSyncError("XLSX first worksheet could not be resolved")


def _xlsx_shared_string_value(
    raw_index: str,
    shared_strings: list[str],
    *,
    limits: ParseLimits,
) -> str:
    max_index_digits = max(1, len(str(max(limits.max_xlsx_shared_strings - 1, 0))))
    if len(raw_index) > min(
        limits.max_numeric_chars, max_index_digits
    ) or not _ASCII_INTEGER_RE.fullmatch(raw_index):
        raise SourceSyncError("XLSX shared string reference is invalid")
    try:
        return shared_strings[int(raw_index)]
    except (IndexError, ValueError) as exc:
        raise SourceSyncError("XLSX shared string reference is invalid") from exc


def _xlsx_cell_value(
    cell: ElementTree.Element,
    shared_strings: list[str],
    *,
    limits: ParseLimits,
) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(".//{*}t")
        return _xlsx_text(inline) if inline is not None else ""
    value = cell.find("{*}v")
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        return _xlsx_shared_string_value(value.text, shared_strings, limits=limits)
    if cell_type == "b":
        if value.text not in {"0", "1"}:
            raise SourceSyncError("XLSX boolean cell value is invalid")
        return "true" if value.text == "1" else "false"
    return value.text


def _xlsx_row_values(
    row: ElementTree.Element,
    shared_strings: list[str],
    cell_count: int,
    *,
    limits: ParseLimits,
) -> tuple[list[str], int]:
    values: list[str] = []
    seen_columns: set[int] = set()
    for cell in row.findall("{*}c"):
        cell_count += 1
        if cell_count > limits.max_xlsx_cells:
            raise SourceSyncError("The XLSX file contains too many cells")
        column = _xlsx_column_index(cell.attrib.get("r", ""), limits=limits)
        if column in seen_columns:
            raise SourceSyncError("XLSX row contains duplicate cell references")
        seen_columns.add(column)
        while len(values) <= column:
            values.append("")
        cell_value = _xlsx_cell_value(cell, shared_strings, limits=limits).strip()
        if len(cell_value) > limits.max_cell_chars:
            raise SourceSyncError("The XLSX file contains a cell that is too large")
        values[column] = cell_value
    return values, cell_count


def _read_xlsx_sheet_rows(
    sheet: zipfile.ZipExtFile,
    shared_strings: list[str],
    *,
    limits: ParseLimits,
) -> list[list[str]]:
    rows: list[list[str]] = []
    cell_count = 0
    for _event, row in ElementTree.iterparse(sheet, events=("end",)):
        if row.tag.rsplit("}", 1)[-1] != "row":
            continue
        if len(rows) >= limits.max_xlsx_rows:
            raise SourceSyncError(f"The XLSX file contains more than {limits.max_source_rows} rows")
        values, cell_count = _xlsx_row_values(
            row,
            shared_strings,
            cell_count,
            limits=limits,
        )
        rows.append(values)
        row.clear()
    return rows


def _xlsx_rows(content: bytes, *, limits: ParseLimits) -> list[list[str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as workbook:
            _validate_xlsx_archive(workbook, limits=limits)
            shared_strings = _xlsx_shared_strings(workbook, limits=limits)
            sheet_path = _xlsx_first_sheet_path(workbook, limits=limits)
            sheet_info = _xlsx_member_info(workbook, sheet_path)
            _validate_xlsx_member(sheet_info, limits=limits)
            with workbook.open(sheet_info) as sheet:
                return _read_xlsx_sheet_rows(sheet, shared_strings, limits=limits)
    except zipfile.BadZipFile as exc:
        raise SourceSyncError("The XLSX file could not be opened") from exc
    except KeyError as exc:
        raise SourceSyncError("The XLSX first worksheet could not be read") from exc
    except ElementTree.ParseError as exc:
        raise SourceSyncError("The XLSX first worksheet is malformed") from exc


def parse_source_xlsx(
    content: bytes,
    *,
    limits: ParseLimits = DEFAULT_PARSE_LIMITS,
) -> tuple[str, list[ParsedSourceRow]]:
    if not content:
        raise SourceSyncError("The uploaded XLSX is empty")
    if len(content) > limits.max_source_bytes:
        raise SourceSyncError("The uploaded XLSX is larger than 5 MB")
    rows = _xlsx_rows(content, limits=limits)
    normalized_csv = io.StringIO()
    writer = csv.writer(normalized_csv)
    writer.writerows(rows)
    return normalized_csv.getvalue(), _parse_source_rows(rows, limits=limits)


def parse_source_file(
    filename: str,
    content: bytes,
    *,
    limits: ParseLimits = DEFAULT_PARSE_LIMITS,
) -> tuple[str, list[ParsedSourceRow]]:
    suffix = filename.rsplit(".", 1)[-1].casefold() if "." in filename else "csv"
    if suffix == "xlsx":
        return parse_source_xlsx(content, limits=limits)
    if suffix == "csv":
        return parse_source_csv(content, limits=limits)
    raise SourceSyncError("Upload must be a CSV or XLSX file")


__all__ = [
    "DEFAULT_PARSE_LIMITS",
    "FIELD_ALIASES",
    "ParseLimits",
    "REQUIRED_FIELDS",
    "parse_hd",
    "parse_runtime",
    "parse_source_csv",
    "parse_source_file",
    "parse_source_xlsx",
    "parse_year",
]
