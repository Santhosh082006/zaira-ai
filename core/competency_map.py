import json
import os
from typing import List, Optional
from core.schemas import Competency, CompetencyCoverage

class CompetencyMap:
    """
    Loads and manages the competency domain structure.
    Used for initializing coverage state and linking questions to required evidence.
    """
    def __init__(self, filepath: Optional[str] = None):
        if filepath is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(base_dir, "competencies.json")
            
        self.filepath = filepath
        self.competencies: List[Competency] = []
        self.load_competencies()

    def load_competencies(self):
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Competency map file not found at: {self.filepath}")
            
        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.competencies = [Competency(**c) for c in data]

    def get_competency_by_id(self, comp_id: str) -> Optional[Competency]:
        for c in self.competencies:
            if c.id == comp_id:
                return c
        return None

    def get_competencies_by_category(self, category: str) -> List[Competency]:
        return [c for c in self.competencies if c.category.upper() == category.upper()]

    def initialize_coverage_model(self, required_competency_ids: List[str]) -> List[CompetencyCoverage]:
        """
        Returns a list of clean CompetencyCoverage tracking objects 
        for a new interview session.
        """
        coverage_list = []
        for cid in required_competency_ids:
            if self.get_competency_by_id(cid):
                coverage_list.append(CompetencyCoverage(
                    competency_id=cid,
                    evidence_found=[],
                    status="not_tested"
                ))
        return coverage_list

    def evaluate_coverage(
        self,
        current_coverage: CompetencyCoverage,
        new_evidence: List[str],
        explicit_status: Optional[str] = None,
        explicit_score: Optional[float] = None,
        findings: Optional[List[str]] = None
    ) -> CompetencyCoverage:
        """
        Updates a coverage record with new evidence, explicit rubric status, and score.
        Status rubrics: 'not_tested', 'needs_improvement', 'partially_demonstrated', 'demonstrated'
        """
        current_coverage.evidence_found.extend(new_evidence)
        # Deduplicate
        current_coverage.evidence_found = list(set(current_coverage.evidence_found))
        
        if findings:
            current_coverage.findings.extend(findings)
            current_coverage.findings = list(set(current_coverage.findings))

        if explicit_score is not None:
            current_coverage.score = explicit_score

        if explicit_status in ["demonstrated", "partially_demonstrated", "needs_improvement", "not_tested"]:
            current_coverage.status = explicit_status
        else:
            count = len(current_coverage.evidence_found)
            if count == 0:
                current_coverage.status = "not_tested"
            elif count == 1:
                current_coverage.status = "partially_demonstrated"
            elif count >= 2:
                current_coverage.status = "demonstrated"
            
        return current_coverage
