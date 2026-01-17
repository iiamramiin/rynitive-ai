"""
Enhanced CSV Shareability Scanner
Combines robust PII detection with smart heuristics and performance optimizations
"""

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
import pandas as pd
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import re


# Direct identifier entity types
DIRECT_ID_ENTITIES = {
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "US_SSN",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "PERSON",
    "LOCATION",
    "US_DRIVER_LICENSE",
    "US_PASSPORT",
}

# Column name hints for quasi-identifiers
QUASI_HINTS = {
    "dob": ["dob", "date_of_birth", "birth", "birthday", "birthdate", "born"],
    "zip": ["zip", "zipcode", "postal", "postcode", "zip_code"],
    "age": ["age", "age_years", "yrs_old"],
    "gender": ["gender", "sex"],
    "location": ["city", "state", "county", "country", "region", "lat", "lon", "latitude", "longitude"],
    "race_ethnicity": ["race", "ethnicity", "ethnic", "nationality"],
}

# Column name hints for direct identifiers
DIRECT_HINTS = {
    "email": ["email", "e-mail", "mail"],
    "phone": ["phone", "mobile", "cell", "telephone", "tel"],
    "name": ["name", "first_name", "last_name", "fullname", "full_name", "firstname", "lastname"],
    "address": ["address", "street", "st", "ave", "avenue", "road", "rd", "boulevard"],
    "ssn": ["ssn", "social", "social_security"],
    "id": ["passport", "driver", "license", "mrn", "member_id", "account", "customer_id", "patient_id", "user_id"],
}


@dataclass
class ColumnFinding:
    """Results for a single column"""
    column: str
    dtype: str
    non_null: int
    unique: int
    unique_ratio: float
    pii_counts: Dict[str, int]
    pii_examples: Dict[str, List[str]]
    has_direct_hint: bool
    quasi_hints: List[str]
    high_uniqueness: bool


class ShareabilityScanner:
    def __init__(self):
        """Initialize Presidio analyzer with custom recognizers"""
        self.analyzer = AnalyzerEngine()
        
        # Add custom medical record number pattern
        mrn_pattern = PatternRecognizer(
            supported_entity="MEDICAL_RECORD_NUMBER",
            patterns=[
                Pattern("MRN", r"\b(MRN|mrn)[:\s-]*([A-Z0-9]{6,10})\b", 0.85),
                Pattern("PATIENT_ID", r"\b(P|PAT)[0-9]{6,9}\b", 0.75)
            ]
        )
        self.analyzer.registry.add_recognizer(mrn_pattern)
        
        # Add these to direct identifiers
        DIRECT_ID_ENTITIES.add("MEDICAL_RECORD_NUMBER")
    
    def scan_csv(
        self, 
        df: pd.DataFrame, 
        filename: str,
        max_sample_per_column: int = 100
    ) -> dict:
        """
        Main scanning function with performance optimizations
        
        Args:
            df: pandas DataFrame to scan
            filename: original filename
            max_sample_per_column: max cells to scan per column (for speed)
        
        Returns:
            Complete shareability analysis dict
        """
        
        results = {
            'filename': filename,
            'row_count': len(df),
            'column_count': len(df.columns),
            'risky_columns': [],
            'pii_by_column': {},
            'pii_count': 0,
            'direct_identifier_columns': [],
            'quasi_identifiers': [],
            'high_uniqueness_columns': [],
            'combo_uniqueness_ratio': None,
            'risk_factors': [],
            'readiness_level': 'GREEN',
            'recommendations': []
        }
        
        column_findings: List[ColumnFinding] = []
        
        print(f"Scanning {len(df.columns)} columns...")
        
        # Scan each column
        for col in df.columns:
            finding = self._scan_column(df[col], col, max_sample_per_column)
            column_findings.append(finding)
            
            # Track risky columns
            if finding.pii_counts or finding.has_direct_hint or finding.quasi_hints:
                results['risky_columns'].append(col)
                results['pii_by_column'][col] = {
                    'pii_types': finding.pii_counts,
                    'pii_count': sum(finding.pii_counts.values()),
                    'examples': finding.pii_examples,
                    'has_pii': bool(finding.pii_counts),
                    'is_quasi_id': bool(finding.quasi_hints),
                    'percentage_with_pii': self._calculate_percentage(finding),
                    'unique_ratio': finding.unique_ratio
                }
                results['pii_count'] += sum(finding.pii_counts.values())
            
            # Track direct identifiers
            if finding.has_direct_hint or any(
                pii in DIRECT_ID_ENTITIES for pii in finding.pii_counts.keys()
            ):
                results['direct_identifier_columns'].append(col)
            
            # Track quasi-identifiers
            if finding.quasi_hints:
                results['quasi_identifiers'].append(col)
            
            # Track high uniqueness columns
            if finding.high_uniqueness:
                results['high_uniqueness_columns'].append(col)
        
        # Calculate combination uniqueness for quasi-identifiers
        results['combo_uniqueness_ratio'] = self._calculate_combo_uniqueness(
            df, results['quasi_identifiers']
        )
        
        # Calculate risk factors
        results['risk_factors'] = self._calculate_risk_factors(results, df)
        
        # Determine readiness level
        results['readiness_level'] = self._determine_readiness(results)
        
        # Generate recommendations
        results['recommendations'] = self._generate_recommendations(results, df)
        
        return results
    
    def _normalize_column_name(self, col: str) -> str:
        """Normalize column name for hint matching"""
        return str(col).strip().lower().replace(" ", "_").replace("-", "_")
    
    def _detect_hints(self, col_name: str) -> Tuple[bool, List[str]]:
        """
        Detect if column name suggests direct or quasi identifiers
        
        Returns:
            (has_direct_hint, list_of_quasi_hint_types)
        """
        col_norm = self._normalize_column_name(col_name)
        
        # Check for direct identifier hints
        has_direct = any(
            any(hint in col_norm for hint in hints)
            for hints in DIRECT_HINTS.values()
        )
        
        # Check for quasi-identifier hints
        quasi_matches = [
            hint_type 
            for hint_type, hints in QUASI_HINTS.items()
            if any(hint in col_norm for hint in hints)
        ]
        
        return has_direct, quasi_matches
    
    def _scan_column(
        self, 
        series: pd.Series, 
        col_name: str,
        max_sample: int
    ) -> ColumnFinding:
        """
        Scan a single column with smart sampling
        """
        # Basic stats
        non_null = int(series.notna().sum())
        unique = int(series.nunique(dropna=True))
        unique_ratio = float(unique / non_null) if non_null > 0 else 0.0
        
        # High uniqueness flag (potential identifier)
        high_uniqueness = unique_ratio >= 0.85 and non_null >= 30
        
        # Check column name hints
        has_direct_hint, quasi_hints = self._detect_hints(col_name)
        
        # Sample values for Presidio analysis (smart sampling for performance)
        sample_values = self._sample_column_values(series, max_sample)
        
        # Run PII detection
        pii_counts: Dict[str, int] = {}
        pii_examples: Dict[str, List[str]] = {}
        
        for value in sample_values:
            if not value or len(value.strip()) < 3:
                continue
            
            # Presidio analysis
            findings = self._analyze_text(value)
            
            for finding in findings:
                entity = finding.entity_type
                
                # Only track direct identifiers
                if entity in DIRECT_ID_ENTITIES:
                    pii_counts[entity] = pii_counts.get(entity, 0) + 1
                    
                    # Store example (truncated)
                    if len(pii_examples.get(entity, [])) < 3:
                        if entity not in pii_examples:
                            pii_examples[entity] = []
                        truncated = self._truncate(value, 60)
                        if truncated not in pii_examples[entity]:
                            pii_examples[entity].append(truncated)
        
        return ColumnFinding(
            column=col_name,
            dtype=str(series.dtype),
            non_null=non_null,
            unique=unique,
            unique_ratio=unique_ratio,
            pii_counts=pii_counts,
            pii_examples=pii_examples,
            has_direct_hint=has_direct_hint,
            quasi_hints=quasi_hints,
            high_uniqueness=high_uniqueness
        )
    
    def _sample_column_values(self, series: pd.Series, max_sample: int) -> List[str]:
        """
        Smart sampling: prioritize non-null, unique values
        """
        # Remove nulls
        values = series.dropna()
        
        if values.empty:
            return []
        
        # Convert to string
        values = values.astype(str)
        
        # If small enough, use all
        if len(values) <= max_sample:
            return values.tolist()
        
        # Sample randomly
        return values.sample(n=max_sample, random_state=42).tolist()
    
    def _analyze_text(self, text: str) -> list:
        """
        Analyze text with Presidio, with error handling and confidence filtering
        """
        try:
            # Get all findings
            findings = self.analyzer.analyze(text=text, language='en')
            
            # Filter by confidence score (0.7 = 70% confidence minimum)
            # This dramatically reduces false positives while keeping true PII
            filtered_findings = [f for f in findings if f.score >= 0.7]
            
            return filtered_findings
        except Exception as e:
            # Fail gracefully if Presidio chokes
            return []
    
    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate and clean text for examples"""
        text = text.replace("\n", " ").strip()
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."
    
    def _calculate_percentage(self, finding: ColumnFinding) -> float:
        """Calculate percentage of cells with PII"""
        if finding.non_null == 0:
            return 0.0
        total_pii = sum(finding.pii_counts.values())
        return round((total_pii / finding.non_null) * 100, 1)
    
    def _calculate_combo_uniqueness(
        self, 
        df: pd.DataFrame, 
        quasi_cols: List[str]
    ) -> Optional[float]:
        """
        Calculate uniqueness when combining quasi-identifiers
        High combo uniqueness = easy to re-identify individuals
        """
        if len(quasi_cols) < 2 or len(df) < 20:
            return None
        
        try:
            # Create subset with quasi-identifier columns
            subset = df[quasi_cols].copy()
            
            # Fill nulls and convert to string for comparison
            for col in quasi_cols:
                subset[col] = subset[col].astype(str).fillna("")
            
            # Count unique combinations
            unique_combos = subset.drop_duplicates().shape[0]
            
            # Calculate ratio
            return round(unique_combos / len(df), 3)
        except:
            return None
    
    def _calculate_risk_factors(self, results: dict, df: pd.DataFrame) -> List[str]:
        """
        Identify specific risk factors with enhanced logic
        """
        risks = []
        
        # Direct identifiers found
        if results['direct_identifier_columns']:
            direct_types = set()
            for col_data in results['pii_by_column'].values():
                for pii_type in col_data['pii_types'].keys():
                    if pii_type in DIRECT_ID_ENTITIES:
                        direct_types.add(pii_type)
            
            if direct_types:
                risks.append(
                    f"Direct identifiers found: {', '.join(sorted(direct_types))}"
                )
        
        # Multiple quasi-identifiers
        quasi_count = len(results['quasi_identifiers'])
        if quasi_count >= 3:
            risks.append(
                f"{quasi_count} quasi-identifiers that could re-identify individuals when combined"
            )
        
        # High combination uniqueness
        if results['combo_uniqueness_ratio'] and results['combo_uniqueness_ratio'] > 0.8:
            risks.append(
                f"{int(results['combo_uniqueness_ratio'] * 100)}% of rows are unique on "
                f"quasi-identifier combinations (easy to re-identify)"
            )
        
        # Small dataset
        if len(df) < 100:
            risks.append(
                f"Small dataset size ({len(df)} rows) increases re-identification risk"
            )
        
        # High uniqueness columns
        if results['high_uniqueness_columns']:
            risks.append(
                f"{len(results['high_uniqueness_columns'])} columns with >85% unique values "
                f"(potential identifiers)"
            )
        
        return risks if risks else ["No major risk factors detected"]
    
    def _determine_readiness(self, results: dict) -> str:
        """
        Calculate RED/YELLOW/GREEN readiness level
        """
        # RED: Direct identifiers found
        if results['direct_identifier_columns']:
            return 'RED'
        
        # YELLOW: Multiple quasi-identifiers or high combo uniqueness
        if len(results['quasi_identifiers']) >= 2:
            return 'YELLOW'
        
        if results['combo_uniqueness_ratio'] and results['combo_uniqueness_ratio'] > 0.7:
            return 'YELLOW'
        
        if len(results['high_uniqueness_columns']) >= 2:
            return 'YELLOW'
        
        # GREEN: Low risk
        return 'GREEN'
    
    def _generate_recommendations(self, results: dict, df: pd.DataFrame) -> List[str]:
        """
        Generate actionable recommendations
        """
        recs = []
        
        if results['readiness_level'] == 'RED':
            recs.append("🔴 DO NOT SHARE without removing direct identifiers")
            
            # List specific columns to remove
            if results['direct_identifier_columns']:
                cols_to_remove = results['direct_identifier_columns'][:5]
                recs.append(
                    f"Remove these columns entirely: {', '.join(cols_to_remove)}"
                )
        
        elif results['readiness_level'] == 'YELLOW':
            recs.append("🟡 CAUTION: Apply these fixes before sharing")
            
            # Quasi-identifier recommendations
            if len(results['quasi_identifiers']) >= 3:
                recs.append(
                    "Generalize quasi-identifiers: use age ranges (e.g., 30-39) instead of exact ages, "
                    "3-digit ZIP codes instead of 5-digit, broader categories for race/ethnicity"
                )
            
            # High uniqueness recommendations
            if results['high_uniqueness_columns']:
                recs.append(
                    f"Review high-uniqueness columns ({', '.join(results['high_uniqueness_columns'][:3])}) "
                    f"- consider hashing, binning, or removing"
                )
            
            # Date columns
            date_cols = [col for col in df.columns if 'date' in col.lower()]
            if date_cols:
                recs.append(
                    "Shift all dates by a random offset to preserve intervals but hide actual timestamps"
                )
        
        else:  # GREEN
            recs.append("🟢 LOW RISK for typical collaboration scenarios")
            recs.append(
                "Still review the detailed findings and consider your specific use case"
            )
        
        # Universal recommendations
        recs.append(
            "For regulated data (HIPAA/GDPR), consult your compliance team before sharing"
        )
        
        # Small dataset warning
        if len(df) < 50:
            recs.append(
                "⚠️ WARNING: Very small dataset (<50 rows). Consider NOT sharing even after anonymization"
            )
        
        return recs


# Test function
def test_scanner():
    """Test the enhanced scanner"""
    import os
    
    # Load or create test data
    if os.path.exists('test_data.csv'):
        df = pd.read_csv('test_data.csv')
    else:
        data = {
            'name': ['John Smith', 'Jane Doe', 'Bob Johnson'],
            'email': ['john@email.com', 'jane@email.com', 'bob@email.com'],
            'phone': ['555-123-4567', '555-987-6543', '555-456-7890'],
            'age': [45, 32, 67],
            'zip_code': [94025, 10001, 60601],
            'diagnosis': ['Diabetes', 'Hypertension', 'Arthritis']
        }
        df = pd.DataFrame(data)
    
    scanner = ShareabilityScanner()
    results = scanner.scan_csv(df, 'test_data.csv')
    
    print("\n" + "="*70)
    print("ENHANCED SCANNER RESULTS")
    print("="*70)
    print(f"Filename: {results['filename']}")
    print(f"Size: {results['row_count']} rows × {results['column_count']} columns")
    print(f"Readiness Level: {results['readiness_level']}")
    print(f"PII Instances: {results['pii_count']}")
    print(f"\nDirect Identifier Columns: {', '.join(results['direct_identifier_columns'])}")
    print(f"Quasi-Identifier Columns: {', '.join(results['quasi_identifiers'])}")
    print(f"High Uniqueness Columns: {', '.join(results['high_uniqueness_columns'])}")
    
    if results['combo_uniqueness_ratio']:
        print(f"Combo Uniqueness Ratio: {results['combo_uniqueness_ratio']:.1%}")
    
    print("\nRisk Factors:")
    for risk in results['risk_factors']:
        print(f"  • {risk}")
    
    print("\nRecommendations:")
    for rec in results['recommendations']:
        print(f"  {rec}")
    print("="*70 + "\n")
    
    return results


if __name__ == "__main__":
    test_scanner()
