import json
import os
from typing import List, Optional, Dict
from core.schemas import Question

class QuestionBank:
    """
    Loads and manages interview questions.
    Provides filtering based on interview type, level, domain, and missing competencies.
    """
    _runtime_questions: Dict[str, Question] = {}

    def __init__(self, filepath: Optional[str] = None):
        if filepath is None:
            # Default to the questions.json in the same directory as this script
            base_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(base_dir, "questions.json")
        
        self.filepath = filepath
        self.questions: List[Question] = []
        self.load_questions()

    def load_questions(self):
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Question bank file not found at: {self.filepath}")
            
        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.questions = [Question(**q) for q in data]
            for q in self.questions:
                QuestionBank._runtime_questions[q.id] = q

    def add_question(self, question: Question):
        self.questions.append(question)
        QuestionBank._runtime_questions[question.id] = question

    def get_question_by_id(self, question_id: str) -> Optional[Question]:
        for q in self.questions:
            if q.id == question_id:
                return q
        if question_id in QuestionBank._runtime_questions:
            return QuestionBank._runtime_questions[question_id]
        return None

    def filter_questions(
        self,
        interview_type: str,
        level: str,
        exclude_ids: List[str] = None,
        technical_domain: Optional[str] = None,
        target_competency: Optional[str] = None,
        question_type: Optional[str] = None
    ) -> List[Question]:
        """
        Filters the question bank for suitable next questions.
        """
        if exclude_ids is None:
            exclude_ids = []
            
        filtered = []
        for q in self.questions:
            # Check exclusions
            if q.id in exclude_ids:
                continue
                
            # Check interview type
            if interview_type not in q.interview_type:
                continue
                
            # Check level (you might want to allow intermediate for advanced, etc., but strictly matching for now)
            if q.level != level:
                continue
                
            # Check domain
            if technical_domain:
                if q.technical_domain and q.technical_domain.lower() != technical_domain.lower():
                    continue
                if not q.technical_domain and interview_type == "technical":
                    continue
            elif q.technical_domain:
                continue
                
            # Check question type
            if question_type and q.question_type != question_type:
                continue
                
            # Check target competency
            if target_competency and target_competency not in q.competencies:
                continue
                
            filtered.append(q)
            
        return filtered

    def get_intro_question(self, interview_type: str, level: Optional[str] = None, technical_domain: Optional[str] = None) -> Optional[Question]:
        """
        Helper to grab an introductory question for a specific interview type, level, and domain.
        """
        intro_qs = [
            q for q in self.questions 
            if q.question_type == "introduction" 
            and interview_type in q.interview_type
            and (level is None or q.level == level)
            and (technical_domain is None or (q.technical_domain and q.technical_domain.lower() == technical_domain.lower()))
        ]
        if not intro_qs:
            # Relax level constraint
            intro_qs = [
                q for q in self.questions 
                if q.question_type == "introduction" 
                and interview_type in q.interview_type
            ]
        if intro_qs:
            import random
            return random.choice(intro_qs)
        return None
