"""
PDF Report Generator - Simple Version
Uses ReportLab instead of WeasyPrint (works on all platforms)
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import os
from pathlib import Path
import time

def generate_report(scan_results: dict) -> str:
    """
    Generate PDF report from scan results using ReportLab
    Returns: path to generated PDF file
    """
    
    # Create PDF filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #output_path = f"/tmp/shareability_report_{timestamp}.pdf" if os.name != 'nt' else f"{os.environ['TEMP']}\\shareability_report_{timestamp}.pdf"
    # directory where this script lives
    BASE_DIR = Path(__file__).resolve().parent

    # Report/ folder next to the script
    REPORT_DIR = BASE_DIR / "Reports"
    REPORT_DIR.mkdir(exist_ok=True)

    output_path = REPORT_DIR / f"shareability_report_{timestamp}.pdf"
    
    # Create PDF
    #doc = SimpleDocTemplate(output_path, pagesize=letter)
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)  # <-- str() here
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#7c3aed'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=12,
        spaceBefore=20
    )
    
    normal_style = styles['Normal']
    
    # Title with branding
    brand_style = ParagraphStyle(
        'BrandStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#7c3aed'),
        spaceAfter=5,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Logo and brand name
    logo_text_style = ParagraphStyle(
        'LogoText',
        parent=styles['Normal'],
        fontSize=24,
        textColor=colors.HexColor('#7c3aed'),
        spaceAfter=0,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    story.append(Paragraph("🛡️", logo_text_style))
    story.append(Paragraph("Rynitive", brand_style))
    story.append(Spacer(1, 0.1*inch))
    
    # Main title
    story.append(Paragraph("CSV Shareability Report", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Header info
    header_data = [
        ['Dataset:', scan_results['filename']],
        ['Analyzed:', datetime.now().strftime("%B %d, %Y at %I:%M %p")],
        ['Size:', f"{scan_results['row_count']:,} rows × {scan_results['column_count']} columns"],
        ['PII Instances:', str(scan_results['pii_count'])]
    ]
    
    header_table = Table(header_data, colWidths=[1.5*inch, 5*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb'))
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Readiness Assessment
    story.append(Paragraph("Sharing Readiness Assessment", heading_style))
    
    # Readiness box
    readiness_color = {
        'RED': colors.HexColor('#fee2e2'),
        'YELLOW': colors.HexColor('#fef3c7'),
        'GREEN': colors.HexColor('#d1fae5')
    }.get(scan_results['readiness_level'], colors.white)
    
    readiness_text_color = {
        'RED': colors.HexColor('#991b1b'),
        'YELLOW': colors.HexColor('#92400e'),
        'GREEN': colors.HexColor('#065f46')
    }.get(scan_results['readiness_level'], colors.black)
    
    readiness_label = {
        'RED': 'DO NOT SHARE',
        'YELLOW': 'CAUTION REQUIRED',
        'GREEN': 'LOW RISK'
    }.get(scan_results['readiness_level'], 'UNKNOWN')
    
    readiness_data = [[scan_results['readiness_level'], readiness_label]]
    readiness_table = Table(readiness_data, colWidths=[2*inch, 4.5*inch])
    readiness_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), readiness_color),
        ('TEXTCOLOR', (0, 0), (-1, -1), readiness_text_color),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),  # Horizontal center
        ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),  # Vertical center - THIS IS THE KEY FIX
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ('VALIGN', (1, 0), (1, 0), 'MIDDLE'),  # Vertical center for label too
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (0, 0), 24),
        ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (1, 0), (1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
        ('TOPPADDING', (0, 0), (-1, -1), 20),
        ('BOX', (0, 0), (-1, -1), 3, readiness_text_color)
    ]))
    story.append(readiness_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Risk Factors
    story.append(Paragraph("Risk Factors Identified", heading_style))
    for risk in scan_results.get('risk_factors', []):
        story.append(Paragraph(f"• {risk}", normal_style))
        story.append(Spacer(1, 0.1*inch))
    story.append(Spacer(1, 0.2*inch))
    
    # Risky Columns - only show if actual PII was detected
    if scan_results.get('risky_columns') and scan_results.get('pii_count', 0) > 0:
        story.append(Paragraph("Risky Columns Detected", heading_style))
        
        col_data = [['Column Name', 'PII Types', 'Instances', '% Affected']]
        for col, data in scan_results.get('pii_by_column', {}).items():
            # Only include columns that actually have PII instances
            if data.get('pii_count', 0) > 0:
                pii_types = ', '.join(data.get('pii_types', {}).keys()) if data.get('pii_types') else 'Quasi-identifier'
                col_data.append([
                    col,
                    pii_types[:40] + '...' if len(pii_types) > 40 else pii_types,
                    str(data.get('pii_count', 0)),
                    f"{data.get('percentage_with_pii', 0):.1f}%"
                ])
        
        # Only create table if we have data rows beyond the header
        if len(col_data) > 1:
            col_table = Table(col_data, colWidths=[2*inch, 2.5*inch, 1*inch, 1*inch])
            col_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7c3aed')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
            ]))
            story.append(col_table)
            story.append(Spacer(1, 0.3*inch))
    
    # Quasi-Identifiers - only show for YELLOW/RED reports
    if scan_results.get('quasi_identifiers') and scan_results.get('readiness_level') != 'GREEN':
        story.append(Paragraph("Quasi-Identifiers", heading_style))
        story.append(Paragraph("These columns can be combined to re-identify individuals:", normal_style))
        for col in scan_results['quasi_identifiers']:
            story.append(Paragraph(f"• <b>{col}</b>", normal_style))
        story.append(Spacer(1, 0.3*inch))
    
    # Page break before recommendations
    story.append(PageBreak())
    
    # Recommendations
    story.append(Paragraph("Recommendations", heading_style))
    for rec in scan_results.get('recommendations', []):
        story.append(Paragraph(f"• {rec}", normal_style))
        story.append(Spacer(1, 0.15*inch))
    
    story.append(Spacer(1, 0.3*inch))
    
    # Disclaimer box
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=normal_style,
        fontSize=9,
        leading=12
    )
    
    disclaimer_text = """
    <b>⚠️ Important Disclaimer & Limitations</b><br/><br/>
    This report provides <b>automated indicators and recommendations only</b>. 
    It is not a compliance guarantee, legal advice, or substitute for expert review.<br/><br/>
    <b>Known Limitations:</b><br/>
    • PII detection is not 100% accurate (false positives and false negatives occur)<br/>
    • Context-specific risks may not be detected by automated scanning<br/>
    • This tool does not assess legal compliance with HIPAA, GDPR, or other regulations<br/>
    • Detection accuracy: ~85-95% for common PII types, lower for domain-specific identifiers<br/>
    • This tool is designed for <b>de-identified datasets or non-PHI data only</b><br/><br/>
    <b>Your Responsibility:</b><br/>
    Final decisions about data sharing remain with you. For regulated data (HIPAA/GDPR) 
    or high-risk scenarios, consult your compliance team or legal counsel before sharing.<br/><br/>
    This is a <b>scanning and visibility tool</b>, not a compliance service or legal guarantee.
    """
    
    disclaimer_data = [[Paragraph(disclaimer_text, disclaimer_style)]]
    disclaimer_table = Table(disclaimer_data, colWidths=[6.5*inch])
    disclaimer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fef3c7')),
        ('BOX', (0, 0), (-1, -1), 3, colors.HexColor('#f59e0b')),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15)
    ]))
    story.append(disclaimer_table)
    
    # Footer
    story.append(Spacer(1, 0.4*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=normal_style,
        fontSize=9,
        textColor=colors.HexColor('#6b7280'),
        alignment=TA_CENTER
    )
    story.append(Paragraph("<b>Generated by Rynitive - CSV Shareability Checker</b>", footer_style))
    story.append(Paragraph("rynitive.com | support@rynitive.com", footer_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("This report is for informational purposes only and does not constitute legal, compliance, or professional advice.", footer_style))
    
    # Build PDF
    doc.build(story)
    
    print(f"✓ PDF report generated: {output_path}")
    return output_path


def test_report_generator():
    """Test the report generator"""
    from scanner_enhanced import ShareabilityScanner
    import pandas as pd
    
    # Create sample data
    data = {
        'name': ['John Smith', 'Jane Doe', 'Bob Johnson'],
        'email': ['john@email.com', 'jane@email.com', 'bob@email.com'],
        'phone': ['555-123-4567', '555-987-6543', '555-456-7890'],
        'age': [45, 32, 67],
        'zip_code': [94025, 10001, 60601],
        'diagnosis': ['Diabetes', 'Hypertension', 'Arthritis']
    }
    df = pd.DataFrame(data)
    
    # Scan the data
    scanner = ShareabilityScanner()
    results = scanner.scan_csv(df, 'test_sample.csv')
    
    # Generate report
    pdf_path = generate_report(results)
    
    print(f"\n✅ Test report generated successfully!")
    print(f"📄 Open this file to view: {pdf_path}")
    
    return pdf_path


if __name__ == "__main__":
    test_report_generator()
