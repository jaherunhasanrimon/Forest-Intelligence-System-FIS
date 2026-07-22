"""
Automated Report Generation Service
===================================

Compiles executive summary data, renders Jinja2 HTML templates,
and generates PDF reports using ReportLab.
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.models.job import Job
from app.models.aoi import AOI
from app.models.satellite_dataset import SatelliteDataset
from app.models.analysis_result import AnalysisResult

logger = logging.getLogger(__name__)


def generate_executive_summary(aoi: AOI, analysis: AnalysisResult) -> str:
    """
    Constructs an automated diagnostic executive summary paragraph.
    """
    name = aoi.name or "Selected AOI"
    area_ha = float(aoi.area_hectares or 0.0)
    cover_pct = float(analysis.forest_cover_pct or 0.0)
    tree_count = int(analysis.tree_count or 0)
    biomass = float(analysis.biomass_tons or 0.0)
    carbon = float(analysis.carbon_tons or 0.0)
    co2e = float(analysis.co2_equivalent_tons or 0.0)
    health = analysis.health_category or "Unknown"
    score = float(analysis.suitability_score or 0.0)

    summary = (
        f"The Area of Interest '{name}' covering {area_ha:,.2f} hectares was evaluated using multi-temporal "
        f"Sentinel-1 SAR C-Band radar and Sentinel-2 optical imagery. The parcel exhibits a forest canopy "
        f"coverage of {cover_pct:.1f}%, supporting an estimated {tree_count:,} trees and a total dry biomass "
        f"stock of {biomass:,.1f} tonnes. Under IPCC Tier 1 standards, this biomass sequesters approximately "
        f"{carbon:,.1f} tonnes of elemental carbon, representing a carbon dioxide equivalent (CO₂e) offset "
        f"of {co2e:,.1f} tonnes. Overall forest condition is classified as {health} with a Reforestation and "
        f"Conservation Suitability Score of {score:.1f}/100."
    )
    return summary


def render_html_report(job: Job, aoi: AOI, analysis: AnalysisResult, summary_text: str) -> str:
    """
    Renders the Jinja2 HTML template and saves to storage/reports/job_{job_id}_report.html.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(base_dir, "templates")
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("report_pdf.html")

    report_mock_data = {
        "summary_text": summary_text,
        "created_at": datetime.utcnow()
    }

    rendered_html = template.render(
        job=job,
        aoi=aoi,
        analysis=analysis,
        report=report_mock_data
    )

    output_dir = os.path.join(settings.LOCAL_STORAGE_PATH, "reports")
    os.makedirs(output_dir, exist_ok=True)
    html_path = os.path.join(output_dir, f"job_{job.id}_report.html")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    logger.info("Saved HTML report to %s", html_path)
    return html_path


def compile_pdf_with_reportlab(pdf_path: str, job: Job, aoi: AOI, analysis: AnalysisResult, summary_text: str) -> None:
    """
    Builds a PDF report using ReportLab.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1F5C3B")
    )
    
    subtitle_style = ParagraphStyle(
        "ReportSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#5B665D")
    )

    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1B241D"),
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1B241D")
    )

    elements = []

    # Title & Header
    elements.append(Paragraph("Forest Intelligence System (FIS)", title_style))
    elements.append(Paragraph(f"Executive Analysis Report — Job #{job.id}", subtitle_style))
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1F5C3B"), spaceAfter=14))

    # Executive Summary Box
    elements.append(Paragraph("Executive Diagnostic Summary", section_style))
    elements.append(Paragraph(summary_text, body_style))
    elements.append(Spacer(1, 16))

    # Key Metrics Grid Table
    elements.append(Paragraph("Primary Environmental Metrics", section_style))
    
    health_color = colors.HexColor("#1F5C3B") if analysis.health_category == "Healthy" else (
        colors.HexColor("#C9713C") if analysis.health_category == "Stressed" else colors.HexColor("#B23A32")
    )

    metrics_data = [
        [
            Paragraph("<b>Canopy Cover</b>", body_style),
            Paragraph(f"<b>{analysis.forest_cover_pct}%</b>", body_style),
            Paragraph("<b>Forest Health</b>", body_style),
            Paragraph(f"<font color='{health_color.hexval()}'><b>{analysis.health_category}</b></font>", body_style)
        ],
        [
            Paragraph("<b>Estimated Trees</b>", body_style),
            Paragraph(f"{analysis.tree_count:,}", body_style),
            Paragraph("<b>Suitability Score</b>", body_style),
            Paragraph(f"<b>{analysis.suitability_score} / 100</b>", body_style)
        ],
        [
            Paragraph("<b>Dry Biomass</b>", body_style),
            Paragraph(f"{analysis.biomass_tons:,.1f} tonnes", body_style),
            Paragraph("<b>Carbon Stock</b>", body_style),
            Paragraph(f"{analysis.carbon_tons:,.1f} t C", body_style)
        ],
        [
            Paragraph("<b>CO₂e Offset</b>", body_style),
            Paragraph(f"<b>{analysis.co2_equivalent_tons:,.1f} t CO₂e</b>", body_style),
            Paragraph("<b>AOI Surface Area</b>", body_style),
            Paragraph(f"{aoi.area_hectares:,.2f} ha", body_style)
        ]
    ]

    metrics_table = Table(metrics_data, colWidths=[110, 150, 110, 150])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F7F5EF")),
        ('BORDER', (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D4C7")),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(metrics_table)
    elements.append(Spacer(1, 18))

    # Metadata Details Table
    elements.append(Paragraph("AOI & Processing Parameters", section_style))
    meta_data = [
        [Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Value / Specification</b>", body_style)],
        [Paragraph("Parcel Name", body_style), Paragraph(str(aoi.name), body_style)],
        [Paragraph("Observation Window", body_style), Paragraph(f"{job.start_date} to {job.end_date}", body_style)],
        [Paragraph("Satellite Sensors", body_style), Paragraph("Sentinel-1 SAR C-Band + Sentinel-2 Optical", body_style)],
        [Paragraph("Raster Resolution", body_style), Paragraph("10.0m / pixel (10-Band Composite)", body_style)],
        [Paragraph("Report Generated", body_style), Paragraph(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), body_style)]
    ]

    meta_table = Table(meta_data, colWidths=[160, 360])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E8E6DE")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D4C7")),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 20))

    # Footer note
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D8D4C7"), spaceAfter=8))
    elements.append(Paragraph("<font size=8 color='#5B665D'>Generated automatically by Forest Intelligence System (FIS) v1.0.0 — IPCC Tier 1 Standard Compliance</font>", body_style))

    doc.build(elements)
    logger.info("Saved ReportLab PDF report to %s", pdf_path)


def generate_full_report(job_id: int, db: Session) -> Tuple[str, str, str]:
    """
    Main entrypoint: Generates both HTML and PDF report deliverables for a Job.
    Returns:
        tuple (summary_text, html_path, pdf_path)
    """
    db_job = db.query(Job).filter(Job.id == job_id).first()
    if not db_job:
        raise ValueError(f"Job #{job_id} not found in database.")

    db_aoi = db.query(AOI).filter(AOI.id == db_job.aoi_id).first()
    if not db_aoi:
        raise ValueError(f"AOI #{db_job.aoi_id} not found.")

    analysis = db.query(AnalysisResult).filter(AnalysisResult.job_id == job_id).first()
    if not analysis:
        raise ValueError(f"AnalysisResult for Job #{job_id} not found.")

    # 1. Executive Summary
    summary_text = generate_executive_summary(db_aoi, analysis)

    # 2. HTML Report
    html_path = render_html_report(db_job, db_aoi, analysis, summary_text)

    # 3. PDF Report
    output_dir = os.path.join(settings.LOCAL_STORAGE_PATH, "reports")
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"job_{job_id}_report.pdf")

    compile_pdf_with_reportlab(pdf_path, db_job, db_aoi, analysis, summary_text)

    return summary_text, html_path, pdf_path
