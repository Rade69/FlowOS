"""PlanImportService — struktuirani parser FlowOS Markdown plana.

Parsira Markdown plan i kreira DRAFT Plan sa PlanPhase, PlanItem,
PlanItemCriterion i PlanItemDependency zapisima.

NEMA AI/LLM zaključivanja. Parser koristi isključivo regularne izraze
i strukturiranu analizu Markdown heading-a. Nejasnoće se vraćaju
korisniku na potvrdu.
"""

import re
from dataclasses import dataclass, field
from typing import Any


class PlanImportError(ValueError):
    """Greška pri importu plana (npr. plan bez ijedne FLOW stavke).

    Podiže se PRE bilo kakvog DB write-a, tako da transakcija ne ostavlja
    parcijalni import (fail-closed).
    """


# ═══════════════════════════════════════════════════════════════════
# Parsirani tipovi
# ═══════════════════════════════════════════════════════════════════


@dataclass
class ParsedCriterion:
    """Pojedinačni kriterijum iz parsiranog plana."""

    key: str
    description: str


@dataclass
class ParsedDependency:
    """Zavisnost između dve FLOW stavke."""

    depends_on_key: str
    dependency_type: str  # BLOCKS_START, BLOCKS_VERIFICATION, INFORMATIONAL


@dataclass
class ParsedItem:
    """Jedna FLOW stavka iz parsiranog plana."""

    item_key: str  # npr. "FLOW-000"
    title: str  # npr. "Bootstrap repozitorija"
    description: str  # kompletan tekst ispod heading-a
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    sequence: int
    criteria: list[ParsedCriterion] = field(default_factory=list)
    dependencies: list[ParsedDependency] = field(default_factory=list)


@dataclass
class ParsedPhase:
    """Jedna faza iz parsiranog plana."""

    phase_key: str  # npr. "F0", "F1"
    title: str
    sequence: int
    items: list[ParsedItem] = field(default_factory=list)


@dataclass
class ImportResult:
    """Rezultat parsiranja Markdown plana."""

    title: str
    phases: list[ParsedPhase] = field(default_factory=list)
    unclear_sections: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# Parser
# ═══════════════════════════════════════════════════════════════════


class PlanMarkdownParser:
    """Parsira FlowOS Markdown plan u strukturirane ParsedPhase objekte.

    Prepoznaje:
    - ## Faza X — Naziv → ParsedPhase
    - #### FLOW-xxx — Naziv → ParsedItem
    - **Rizik:** HIGH → risk_level
    - **Dokaz:** ... → acceptance kriterijum
    - Obavezno: / liste → dodatni kriterijumi
    - Završiti FLOW-xxx prije FLOW-yyy → zavisnost
    - Reference na druge FLOW-xxx → INFORMATIONAL zavisnosti
    """

    # Regex patterns
    PHASE_HEADING = re.compile(r"^##\s+Faza\s+(\d+)\s*[—\-]\s*(.+)$", re.IGNORECASE)
    ITEM_HEADING = re.compile(r"^####\s+(FLOW-\d+[A-Za-z]?)\s*[—\-]\s*(.+)$", re.IGNORECASE)
    RISK_PATTERN = re.compile(r"\*\*Rizik:\*\*\s*(LOW|MEDIUM|HIGH|CRITICAL)", re.IGNORECASE)
    DEPENDS_PATTERN = re.compile(
        r"(?:Završiti|prije|poslije|zavisi od|nakon)\s+(FLOW-\d+[A-Za-z]?)\s+(?:prije|poslije|prije nego|nakon)\s+(FLOW-\d+[A-Za-z]?)",
        re.IGNORECASE,
    )
    FLOW_REF_PATTERN = re.compile(r"(?<!\w)(FLOW-\d+[A-Za-z]?)(?!\w)")

    def parse(self, markdown: str) -> ImportResult:
        """Glavna metoda parsiranja.

        Args:
            markdown: Kompletan tekst FlowOS plana u Markdown formatu.

        Returns:
            ImportResult sa parsiranim fazama, stavkama i nejasnoćama.
        """
        lines = markdown.split("\n")
        title = self._extract_title(lines)
        sections = self._split_into_sections(lines)

        result = ImportResult(title=title)

        result.phases = self._parse_phase_sections(sections)

        # Sakupi nejasnoće — samo neprepoznati LEVEL-2 (##) heading
        for section in sections:
            heading = section["heading"]
            if (
                heading
                and section["level"] == 2
                and not self.PHASE_HEADING.match(heading)
                and heading not in result.unclear_sections
            ):
                result.unclear_sections.append(heading)

        result.stats = {
            "phases": len(result.phases),
            "items": sum(len(p.items) for p in result.phases),
            "criteria": sum(len(item.criteria) for p in result.phases for item in p.items),
            "dependencies": sum(len(item.dependencies) for p in result.phases for item in p.items),
            "unclear": len(result.unclear_sections),
        }

        return result

    # ── Interni metodi ────────────────────────────────────

    @staticmethod
    def _extract_title(lines: list[str]) -> str:
        """Ekstrahuje naslov plana iz prvog H1 heading-a."""
        for line in lines[:10]:
            if line.startswith("# ") and not line.startswith("## "):
                return line[2:].strip()
        return "FlowOS Plan"

    def _split_into_sections(self, lines: list[str]) -> list[dict[str, Any]]:
        """Deli Markdown na sekcije po heading-ima (## i ####).

        Returns:
            Lista dict-ova sa 'heading', 'level', 'body' (list[str]).
        """
        sections: list[dict[str, Any]] = []
        current_heading: str | None = None
        current_level: int = 0
        current_body: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Detektuj heading
            if stripped.startswith("## ") and not stripped.startswith("### "):
                # Sačuvaj prethodnu sekciju
                if current_heading is not None:
                    sections.append(
                        {
                            "heading": current_heading,
                            "level": current_level,
                            "body": current_body,
                        }
                    )
                current_heading = stripped
                current_level = 2
                current_body = []
            elif stripped.startswith("#### ") and not stripped.startswith("##### "):
                # FLOW stavka — sačuvamo kao pod-sekciju prethodne
                if current_heading is not None:
                    sections.append(
                        {
                            "heading": current_heading,
                            "level": current_level,
                            "body": current_body,
                        }
                    )
                current_heading = stripped
                current_level = 4
                current_body = []
            else:
                current_body.append(line)

        # Poslednja sekcija
        if current_heading is not None:
            sections.append(
                {
                    "heading": current_heading,
                    "level": current_level,
                    "body": current_body,
                }
            )

        return sections

    def _try_parse_phase(self, section: dict[str, Any]) -> ParsedPhase | None:
        """Pokušava da parsira sekciju kao PlanPhase.

        Sekcija može biti ili `## Faza X` (otvara novu fazu)
        ili `#### FLOW-xxx` (stavka unutar trenutne faze).
        """
        heading: str = section["heading"]
        level: int = section["level"]
        _body: list[str] = section["body"]

        # Pokušaj parsirati kao heading faze
        phase_match = self.PHASE_HEADING.match(heading)
        if phase_match and level == 2:
            phase_num = int(phase_match.group(1))
            return ParsedPhase(
                phase_key=f"F{phase_num}",
                title=f"Faza {phase_num} — {phase_match.group(2).strip()}",
                sequence=phase_num,
            )

        return None

    def _parse_phase_sections(self, sections: list[dict[str, Any]]) -> list[ParsedPhase]:
        """Grupiše FLOW stavke u njihove faze."""
        phases: list[ParsedPhase] = []
        current_phase: ParsedPhase | None = None
        item_sequence = 0

        for section in sections:
            heading = section["heading"]
            level = section["level"]
            body = section["body"]

            # Faza heading → nova faza
            phase_match = self.PHASE_HEADING.match(heading)
            if phase_match and level == 2:
                if current_phase:
                    phases.append(current_phase)
                phase_num = int(phase_match.group(1))
                current_phase = ParsedPhase(
                    phase_key=f"F{phase_num}",
                    title=f"Faza {phase_num} — {phase_match.group(2).strip()}",
                    sequence=phase_num,
                )
                item_sequence = 0
                continue

            # FLOW heading → nova stavka u trenutnoj fazi
            item_match = self.ITEM_HEADING.match(heading)
            if item_match and level == 4 and current_phase is not None:
                item = self._parse_item(
                    item_match.group(1), item_match.group(2).strip(), body, item_sequence
                )
                current_phase.items.append(item)
                item_sequence += 1

        if current_phase:
            phases.append(current_phase)

        return phases

    def _parse_item(self, key: str, title: str, body: list[str], sequence: int) -> ParsedItem:
        """Parsira pojedinačnu FLOW stavku iz body-ja."""
        body_text = "\n".join(body)

        risk = self._extract_risk(body_text)
        criteria = self._extract_criteria(body_text)
        dependencies = self._extract_dependencies(body_text, key)

        return ParsedItem(
            item_key=key,
            title=title,
            description=body_text.strip()[:2000],  # Ograniči dužinu
            risk_level=risk,
            sequence=sequence,
            criteria=criteria,
            dependencies=dependencies,
        )

    @staticmethod
    def _extract_risk(text: str) -> str:
        """Ekstrahuje nivo rizika iz teksta."""
        match = PlanMarkdownParser.RISK_PATTERN.search(text)
        if match:
            return match.group(1).upper()
        return "MEDIUM"  # Default

    def _extract_criteria(self, text: str) -> list[ParsedCriterion]:
        """Ekstrahuje acceptance kriterijume.

        Prepoznaje:
        - **Dokaz:** ...
        - Obavezno: / liste
        - numerisane liste posle ključnih reči
        """
        criteria: list[ParsedCriterion] = []
        seen: set[str] = set()

        # 1. **Dokaz:** linija
        dokaz_match = re.search(r"\*\*Dokaz:\*\*\s*(.+)", text)
        if dokaz_match:
            key = "DOKAZ"
            desc = dokaz_match.group(1).strip()
            if desc and key not in seen:
                criteria.append(ParsedCriterion(key=key, description=desc))
                seen.add(key)

        # 2. Obavezno: / **Kriterij:** blok — numerisane liste
        obavezno_match = re.search(
            r"(?:Obavezno|Kriterij(?:um)?)\s*:\s*\n((?:\d+\.\s+.+\n?)+)", text, re.IGNORECASE
        )
        if obavezno_match:
            lines = obavezno_match.group(1).strip().split("\n")
            for i, line in enumerate(lines):
                stripped = line.strip()
                if re.match(r"^\d+\.", stripped):
                    desc = re.sub(r"^\d+\.\s*", "", stripped).strip()
                    if desc and desc not in seen:
                        criteria.append(
                            ParsedCriterion(key=f"REQ-{i + 1:02d}", description=desc[:500])
                        )
                        seen.add(desc)

        # 3. **Ne raditi:** kao negativni kriterijum
        ne_raditi_match = re.search(r"\*\*Ne raditi:\*\*\s*(.+)", text)
        if ne_raditi_match:
            key = "OUT_OF_SCOPE"
            desc = ne_raditi_match.group(1).strip()
            if desc and key not in seen:
                criteria.append(ParsedCriterion(key=key, description=desc))
                seen.add(key)

        return criteria

    def _extract_dependencies(self, text: str, own_key: str) -> list[ParsedDependency]:
        """Ekstrahuje zavisnosti iz teksta.

        Prepoznaje:
        - "Završiti FLOW-103 prije FLOW-104" → BLOCKS_START
        - Druge FLOW reference → INFORMATIONAL (slabije)
        """
        deps: list[ParsedDependency] = []
        seen: set[tuple[str, str]] = set()

        # Eksplicitne zavisnosti: "Završiti X prije Y"
        for match in self.DEPENDS_PATTERN.finditer(text):
            before = match.group(1)
            after = match.group(2)

            if after == own_key:
                pair = (own_key, before)
                if pair not in seen:
                    deps.append(
                        ParsedDependency(depends_on_key=before, dependency_type="BLOCKS_START")
                    )
                    seen.add(pair)
            elif before == own_key:
                # Mi smo preduslov za drugog — ne dodajemo zavisnost na sebe
                pass

        # Reference na druge FLOW stavke → INFORMATIONAL
        refs = self.FLOW_REF_PATTERN.findall(text)
        for ref in refs:
            if ref != own_key and (own_key, ref) not in seen:
                # INFORMATIONAL samo ako nije već BLOCKS_START
                existing = {(d.depends_on_key, d.dependency_type) for d in deps}
                if (ref, "BLOCKS_START") not in existing:
                    pair = (own_key, ref)
                    if pair not in seen:
                        deps.append(
                            ParsedDependency(depends_on_key=ref, dependency_type="INFORMATIONAL")
                        )
                        seen.add(pair)

        return deps


# ═══════════════════════════════════════════════════════════════════
# PlanImportService — orkestrira import u bazu
# ═══════════════════════════════════════════════════════════════════


class PlanImportService:
    """Orkestrira import Markdown plana u SQLite bazu.

    1. Parsira Markdown → ImportResult
    2. Kreira Plan (DRAFT)
    3. Kreira PlanPhase za svaku fazu
    4. Kreira PlanItem za svaku FLOW stavku
    5. Kreira PlanItemCriterion za svaki kriterijum
    6. Kreira PlanItemDependency za svaku zavisnost
    7. Vraća kompletan ImportResult
    """

    def __init__(self, session: Any) -> None:
        from sqlalchemy.orm import Session as _Session

        self._session: _Session = session

    def import_plan(
        self, project_id: str, markdown: str, *, source_artifact_id: str | None = None
    ) -> ImportResult:
        """Parsira Markdown i kreira DRAFT Plan u bazi.

        Args:
            project_id: ID projekta.
            markdown: Kompletan Markdown tekst plana.
            source_artifact_id: ID artefakta koji čuva originalni Markdown.

        Returns:
            ImportResult sa parsiranim stavkama i statistikom.
        """
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanItemCriterion,
            PlanItemDependency,
            PlanPhase,
        )
        from flowos.service.services.plan_progress import PlanProgressService

        # Parsiraj
        parser = PlanMarkdownParser()
        result = parser.parse(markdown)

        # Fail-closed: plan bez ijedne FLOW stavke ne smije ući u bazu.
        parsed_items = sum(len(phase.items) for phase in result.phases)
        if parsed_items == 0:
            raise PlanImportError(
                "Plan ne sadrži nijednu FLOW stavku; očekuje se '#### FLOW-xxxx — naslov'"
            )

        # Kreiraj Plan
        plan = Plan(
            project_id=project_id,
            title=result.title,
            source_artifact_id=source_artifact_id,
            status="DRAFT",
        )
        self._session.add(plan)
        self._session.flush()

        # Mapiranje item_key → PlanItem.id za zavisnosti
        item_id_map: dict[str, str] = {}
        progress = PlanProgressService(self._session)

        for phase_data in result.phases:
            phase = PlanPhase(
                plan_id=plan.id,
                phase_key=phase_data.phase_key,
                title=phase_data.title,
                sequence=phase_data.sequence,
                status="NOT_STARTED",
            )
            self._session.add(phase)
            self._session.flush()

            for item_data in phase_data.items:
                item = PlanItem(
                    plan_phase_id=phase.id,
                    item_key=item_data.item_key,
                    title=item_data.title,
                    description=item_data.description,
                    sequence=item_data.sequence,
                    risk_level=item_data.risk_level,
                    status="NOT_STARTED",
                )
                self._session.add(item)
                self._session.flush()
                item_id_map[item.item_key] = item.id

                # Kriterijumi
                for crit_data in item_data.criteria:
                    criterion = PlanItemCriterion(
                        plan_item_id=item.id,
                        criterion_key=crit_data.key,
                        description=crit_data.description,
                        status="PENDING",
                    )
                    self._session.add(criterion)

                # Inicijalni audit događaj (direktno, bez validate_transition)
                from flowos.service.services.infrastructure.persistence.plan_models import (
                    PlanProgressEvent,
                )

                self._session.add(
                    PlanProgressEvent(
                        plan_item_id=item.id,
                        from_status="NOT_STARTED",
                        to_status="NOT_STARTED",
                        reason="Importovano iz Markdown plana",
                        source="IMPORTER",
                    )
                )

        # Zavisnosti (drugi prolaz — svi ID-jevi su poznati)
        for phase_data in result.phases:
            for item_data in phase_data.items:
                item_id = item_id_map[item_data.item_key]
                for dep_data in item_data.dependencies:
                    depends_on_id = item_id_map.get(dep_data.depends_on_key)
                    if depends_on_id:
                        # Proveri ciklus
                        try:
                            progress.check_cycle(item_id, depends_on_id)
                        except Exception:
                            result.unclear_sections.append(
                                f"Ciklična zavisnost ignorisana: "
                                f"{item_data.item_key} → {dep_data.depends_on_key}"
                            )
                            continue

                        dep = PlanItemDependency(
                            plan_item_id=item_id,
                            depends_on_plan_item_id=depends_on_id,
                            dependency_type=dep_data.dependency_type,
                        )
                        self._session.add(dep)

        self._session.flush()
        return result
