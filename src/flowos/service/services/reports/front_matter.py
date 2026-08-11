"""Strict YAML front-matter parser za agent_reports Markdown artefakte.

Parser je pure komponenta Phase 2 ingestion toka: čita samo početni YAML
front matter, validira canonical contract i ne zaključuje ništa iz Markdown
tijela.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

import yaml  # type: ignore[import-untyped]


class AgentReportFrontMatterErrorCode(StrEnum):
    LEGACY_NO_FRONT_MATTER = "LEGACY_NO_FRONT_MATTER"
    NEEDS_IDENTITY = "NEEDS_IDENTITY"
    INVALID = "INVALID"


class AgentReportFrontMatterError(ValueError):
    """Validaciona greška canonical front matter ugovora."""

    def __init__(self, code: AgentReportFrontMatterErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AgentReportFrontMatter:
    flowos_report_version: int
    report_id: str
    session_id: str
    report_type: str
    tasks: tuple[str, ...]
    created_at: datetime
    work_status: str | None = None


class _NoDuplicateSafeLoader(yaml.SafeLoader):
    """Safe YAML loader koji odbija duplicate mapping ključeve."""


def _construct_mapping_without_duplicates(loader: yaml.Loader, node: yaml.nodes.MappingNode):
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key ({key!r})",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=False)
    return mapping


_NoDuplicateSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_without_duplicates,
)


class AgentReportFrontMatterParser:
    """Validira canonical FlowOS report YAML front matter."""

    _REQUIRED_KEYS = {
        "flowos_report_version",
        "report_id",
        "session_id",
        "report_type",
        "tasks",
        "created_at",
    }
    _OPTIONAL_KEYS = {"work_status", "agent", "model", "commits"}
    _REPORT_TYPES = {"implementation", "fix", "review", "analysis"}
    _WORK_STATUSES = {"completed", "partial", "blocked"}
    _WORK_STATUS_REQUIRED_FOR = {"implementation", "fix"}

    def parse_text(self, markdown: str) -> AgentReportFrontMatter:
        yaml_text = self._extract_front_matter(markdown)
        try:
            raw = yaml.load(yaml_text, Loader=_NoDuplicateSafeLoader)
        except yaml.YAMLError as exc:
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                f"Neispravan YAML front matter: {exc}",
            ) from exc

        if not isinstance(raw, dict):
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                "YAML front matter mora biti mapping.",
            )

        keys = set(raw)
        missing = self._REQUIRED_KEYS - keys
        if "report_id" in missing:
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.NEEDS_IDENTITY,
                "YAML front matter nema report_id.",
            )
        if missing:
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                f"Nedostaju obavezna YAML polja: {sorted(missing)}",
            )

        unknown = keys - self._REQUIRED_KEYS - self._OPTIONAL_KEYS
        if unknown:
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                f"Nepoznata YAML polja: {sorted(unknown)}",
            )

        version = raw["flowos_report_version"]
        if version != 1:
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                "flowos_report_version mora biti 1.",
            )

        report_id = self._parse_uuid(raw["report_id"], "report_id")
        session_id = self._parse_session_id(raw["session_id"])
        report_type = self._parse_report_type(raw["report_type"])
        tasks = self._parse_tasks(raw["tasks"])
        created_at = self._parse_created_at(raw["created_at"])
        work_status = self._parse_work_status(raw.get("work_status"), report_type)

        return AgentReportFrontMatter(
            flowos_report_version=version,
            report_id=report_id,
            session_id=session_id,
            report_type=report_type,
            tasks=tasks,
            created_at=created_at,
            work_status=work_status,
        )

    def _extract_front_matter(self, markdown: str) -> str:
        lines = markdown.splitlines()
        if not lines or lines[0].strip() != "---":
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.LEGACY_NO_FRONT_MATTER,
                "Markdown nema početni YAML front matter.",
            )
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                return "\n".join(lines[1:idx])
        raise AgentReportFrontMatterError(
            AgentReportFrontMatterErrorCode.INVALID,
            "YAML front matter nema završni delimiter.",
        )

    def _parse_uuid(self, value: object, field: str) -> str:
        if not isinstance(value, str):
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                f"{field} mora biti UUID string.",
            )
        try:
            return str(UUID(value))
        except ValueError as exc:
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                f"{field} nije validan UUID.",
            ) from exc

    def _parse_session_id(self, value: object) -> str:
        if value == "unknown":
            return "unknown"
        return self._parse_uuid(value, "session_id")

    def _parse_report_type(self, value: object) -> str:
        if not isinstance(value, str) or value not in self._REPORT_TYPES:
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                f"report_type mora biti jedan od {sorted(self._REPORT_TYPES)}.",
            )
        return value

    def _parse_tasks(self, value: object) -> tuple[str, ...]:
        if (
            not isinstance(value, list)
            or not value
            or any(not isinstance(item, str) or not item.strip() for item in value)
        ):
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                "tasks mora biti neprazna lista stringova.",
            )
        tasks = tuple(item.strip() for item in value)
        if "unassigned" in tasks and tasks != ("unassigned",):
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                "unassigned mora biti jedini tasks element ako se koristi.",
            )
        return tasks

    def _parse_created_at(self, value: object) -> datetime:
        if isinstance(value, datetime):
            created_at = value
        elif isinstance(value, str):
            try:
                created_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise AgentReportFrontMatterError(
                    AgentReportFrontMatterErrorCode.INVALID,
                    "created_at mora biti validan ISO-8601 timestamp.",
                ) from exc
        else:
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                "created_at mora biti timezone-aware ISO-8601 timestamp.",
            )

        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                "created_at mora biti timezone-aware.",
            )
        return created_at

    def _parse_work_status(self, value: object, report_type: str) -> str | None:
        if value is None:
            if report_type in self._WORK_STATUS_REQUIRED_FOR:
                raise AgentReportFrontMatterError(
                    AgentReportFrontMatterErrorCode.INVALID,
                    f"work_status je obavezan za report_type={report_type}.",
                )
            return None
        if not isinstance(value, str) or value not in self._WORK_STATUSES:
            raise AgentReportFrontMatterError(
                AgentReportFrontMatterErrorCode.INVALID,
                f"work_status mora biti jedan od {sorted(self._WORK_STATUSES)}.",
            )
        return value
