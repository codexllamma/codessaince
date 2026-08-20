import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import inch

def create_complex_pdf(filename: str):
    # Initialize a document that automatically handles page flow
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    # Custom font styles to mimic a bureaucratic document
    title_style = styles['Title']
    title_style.fontName = 'Helvetica-Bold'
    
    heading_style = styles['Heading2']
    heading_style.textColor = colors.darkblue
    
    body_style = styles['Normal']
    body_style.fontName = 'Helvetica'
    body_style.fontSize = 10
    body_style.leading = 14
    body_style.spaceAfter = 10
    
    small_print = ParagraphStyle(
        "SmallPrint",
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        textColor=colors.gray
    )

    story = []

    # 1. Title
    story.append(Paragraph("GOVERNMENT CIRCULAR - OFFICIAL NOTIFICATION", title_style))
    story.append(Spacer(1, 20))

    # 2. Two-Column Header Layout (Using a borderless table for alignment)
    header_data = [
        [
            Paragraph("<b>Reference No:</b> GOV-IND-2026/08", body_style),
            Paragraph("<b>Date:</b> 20-August-2026", body_style)
        ],
        [
            Paragraph("<b>Department:</b> Ministry of Finance", body_style),
            Paragraph("<b>Status:</b> URGENT / MANDATORY", body_style)
        ],
        [
            Paragraph("<b>Issued By:</b> Under Secretary", body_style),
            Paragraph("<b>Contact:</b> admin@finance.gov.in", body_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[3.2*inch, 3.2*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 20))

    # 3. Main Body Text - Dense Paragraphs
    story.append(Paragraph("Subject: Extensive Allocation of Funds for Rural Development Scheme 2026-2027", heading_style))
    
    paragraphs = [
        "This circular mandates all regional offices to begin the disbursement of funds under the newly expanded PM-Rural-Care initiative. This directive supersedes all previous communications regarding the FY 2026-2027 rural budget allocation. Strict compliance is required, and all regional directors must ensure that beneficiary accounts are thoroughly verified through the centralized e-verification portal before any financial transfers are initiated.",
        "Under Section 4(a) of the Rural Finance Act, state-level nodes must submit a weekly reconciliation report to the central dashboard. Failure to comply with the mandated reporting frequency will result in an immediate suspension of the subsequent funding tranche. The Ministry has allocated an aggregate budget of INR 45,000 Crores for this fiscal cycle, encompassing agriculture subsidies, water harvesting infrastructure, and rural tech grants.",
        "Regional managers are hereby instructed to cross-reference all beneficiary details with the authorized state registry. Any discrepancies identified during the audit phase must be flagged to the Central Vigilance Committee within 48 hours. Furthermore, all physical records generated during this exercise must be digitized and uploaded to the Document Management System (DMS) with appropriate metadata."
    ]
    
    for p in paragraphs:
        story.append(Paragraph(p, body_style))
        
    story.append(Spacer(1, 15))

    # 4. Expanded Table Layout
    story.append(Paragraph("Authorized Scheme Limits and Deadlines", heading_style))
    
    table_data = [
        ["Scheme Name", "Beneficiary Tier", "Amount (INR)", "Deadline", "Audit Reqd"],
        ["PM-Rural-Care", "Tier 1 (Farmers)", "12,500.00", "31-10-2026", "Yes"],
        ["Agri-Tech Subsidy", "Tier 2 (Co-ops)", "50,000.00", "15-11-2026", "Yes"],
        ["Water Harvesting", "Tier 1 & 2", "8,000.00", "01-12-2026", "No"],
        ["Solar Pump Grant", "Tier 3 (Panchayats)", "1,25,000.00", "10-01-2027", "Yes"],
        ["Seed Distribution", "Tier 1 (Farmers)", "3,500.00", "28-02-2027", "No"],
        ["Livestock Health", "Tier 2 (Co-ops)", "15,000.00", "15-03-2027", "Yes"]
    ]
    
    data_table = Table(table_data, colWidths=[1.6*inch, 1.4*inch, 1.1*inch, 1*inch, 0.9*inch])
    data_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e4053')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f2f3f4')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'), # Align money values to the right
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(data_table)
    
    # 5. Trigger a Page Break to test multi-page extraction
    story.append(PageBreak())
    
    # 6. Page 2 Extensive Text & Fine Print
    story.append(Paragraph("Annexure I: Compliance and Legal Framework", heading_style))
    
    annexure_text = [
        "<b>1. Data Privacy and Storage:</b> All beneficiary information collected during the disbursement process must be handled strictly in accordance with the Data Protection Guidelines of 2025. Data must be encrypted at rest and in transit.",
        "<b>2. Grievance Redressal:</b> Each district must establish a dedicated grievance redressal cell. Beneficiaries must be provided with a toll-free number and a physical address to submit complaints regarding delayed or denied payments.",
        "<b>3. Independent Audits:</b> A third-party auditor will randomly select 5% of all approved applications for a forensic review. Regional offices must retain physical copies of submitted KYC documents for a minimum of 7 years.",
        "<b>4. Force Majeure:</b> In the event of natural disasters affecting the targeted districts, the disbursement deadlines may be extended by a maximum of 45 days, subject to approval from the Central Emergency Relief Board."
    ]
    
    for item in annexure_text:
        story.append(Paragraph(item, body_style))
        story.append(Spacer(1, 5))
        
    story.append(Spacer(1, 30))

    # Footer Metadata (Testing small font and punctuation retention)
    story.append(Paragraph("CONFIDENTIAL: This document contains proprietary government data. Unauthorized distribution is strictly prohibited.", small_print))
    story.append(Paragraph("Generated by IndicGov-Sentinel System. UUID: 9f86d081884c7d659a2feaa0c55ad015", small_print))
    story.append(Paragraph("System IP Trace: 192.168.1.104 | Operator ID: OP-77291-XZ", small_print))

    # Build the PDF
    doc.build(story)
    print(f"[+] Successfully generated extensive, multi-page test PDF: {filename}")

if __name__ == "__main__":
    create_complex_pdf("complex_layout_test.pdf")