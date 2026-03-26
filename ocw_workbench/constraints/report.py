from __future__ import annotations

from dataclasses import dataclass, field

from ocw_workbench.constraints.models import ConstraintFinding


@dataclass
class ConstraintReport:
    errors: list[ConstraintFinding] = field(default_factory=list)
    warnings: list[ConstraintFinding] = field(default_factory=list)

    def add(self, finding: ConstraintFinding) -> None:
        if finding.severity == "error":
            self.errors.append(finding)
        else:
            self.warnings.append(finding)

    def to_dict(self) -> dict:
        return {
            "errors": [finding.to_dict() for finding in self.errors],
            "warnings": [finding.to_dict() for finding in self.warnings],
            "summary": {
                "error_count": len(self.errors),
                "warning_count": len(self.warnings),
                "total_count": len(self.errors) + len(self.warnings),
            },
        }
