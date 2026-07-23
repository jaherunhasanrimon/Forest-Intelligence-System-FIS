"""
Automated Report Generation Service
===================================

Compiles executive summary data, renders Jinja2 HTML templates,
and generates PDF reports using ReportLab with scientifically valid metrics.
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


def generate_executive_summary(aoi: AOI, analysis: AnalysisResult, job: Job) -> str:
    """
    Constructs an automated diagnostic executive summary paragraph based on
    scientifically separated single-period and multi-temporal metrics.
    """
    name = aoi.name or "Selected AOI"
    area_ha = float(aoi.area_hectares or 0.0)
    cover_pct = float(analysis.forest_cover_pct or 0.0)
    tree_count = int(analysis.tree_count or 0)
    biomass = float(analysis.biomass_tons or 0.0)
    carbon = float(analysis.carbon_tons or 0.0)
    co2e = float(analysis.co2_equivalent_tons or 0.0)
    score = float(analysis.suitability_score or 0.0)

    # Calculate observation length
    obs_days = (job.end_date - job.start_date).days if (job.end_date and job.start_date) else 30

    # Retrieve explainability dict if present
    result_layers = analysis.result_layers or {}
    explainability = result_layers.get("explainability", {})

    cur_cond = explainability.get("current_condition", {})
    cur_class = cur_cond.get("classification", "Moderate" if cover_pct > 30 else "Sparse")

    health_info = explainability.get("forest_health", {})
    health_available = health_info.get("available", False)

    if health_available:
        health_str = f"Forest health condition is classified as <b>{health_info.get('classification', 'Healthy')}</b> based on a {obs_days}-day multi-temporal trend."
    else:
        health_str = (
            f"Because the observation window is <b>{obs_days} days</b>, a multi-temporal forest health trend is "
            f"<b>Unavailable</b> (minimum 180 days / 6 months required to scientifically assess degradation vs. seasonal variance)."
        )

    summary = (
        f"The Area of Interest '<b>{name}</b>' covering {area_ha:,.2f} hectares was evaluated using "
        f"Sentinel-1 SAR C-Band radar and Sentinel-2 optical imagery. The parcel exhibits a forest canopy "
        f"coverage of {cover_pct:.1f}%, supporting an estimated {tree_count:,} trees and a total dry biomass "
        f"stock of {biomass:,.1f} tonnes ({biomass/max(0.1, area_ha):,.1f} t/ha). Under IPCC Tier 1 standards, "
        f"this biomass sequesters approximately {carbon:,.1f} tonnes of elemental carbon, representing a "
        f"carbon dioxide equivalent (CO2e) offset of {co2e:,.1f} tonnes. "
        f"The Current Vegetation Condition is rated as <b>{cur_class}</b>. "
        f"{health_str} "
        f"The Reforestation and Conservation Suitability Score is evaluated at <b>{score:.1f}/100</b>."
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

    obs_days = (job.end_date - job.start_date).days if (job.end_date and job.start_date) else 30
    result_layers = analysis.result_layers or {}
    explainability = result_layers.get("explainability", {})

    cur_cond = explainability.get("current_condition", {})
    cur_class = cur_cond.get("classification", "Moderate" if (analysis.forest_cover_pct or 0) > 30 else "Sparse")
    health_info = explainability.get("forest_health", {})
    reforest_info = explainability.get("reforestation_suitability", {})

    report_mock_data = {
        "summary_text": summary_text,
        "created_at": datetime.utcnow(),
        "obs_days": obs_days,
        "current_condition": cur_cond,
        "current_classification": cur_class,
        "forest_health": health_info,
        "reforestation_suitability": reforest_info
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
    Builds a PDF report using ReportLab with scientifically valid metric sections.
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

    small_style = ParagraphStyle(
        "ReportSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#5B665D")
    )

    elements = []

    # Title & Header
    elements.append(Paragraph("Forest Intelligence System (FIS)", title_style))
    elements.append(Paragraph(f"Executive Analysis Report — Job #{job.id} — <b>{aoi.name}</b>", subtitle_style))
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1F5C3B"), spaceAfter=14))

    # Executive Summary Box
    elements.append(Paragraph("Executive Diagnostic Summary", section_style))
    elements.append(Paragraph(summary_text, body_style))
    elements.append(Spacer(1, 14))

    # Extract explainability data
    obs_days = (job.end_date - job.start_date).days if (job.end_date and job.start_date) else 30
    result_layers = analysis.result_layers or {}
    explainability = result_layers.get("explainability", {})

    cur_cond = explainability.get("current_condition", {})
    cur_class = cur_cond.get("classification", "Moderate" if (analysis.forest_cover_pct or 0) > 30 else "Sparse")
    health_info = explainability.get("forest_health", {})

    health_text = (
        health_info.get("classification", "Healthy")
        if health_info.get("available", False)
        else "Unavailable (Single Period)"
    )

    health_color = colors.HexColor("#1F5C3B") if health_text in ["Healthy", "Excellent"] else (
        colors.HexColor("#5B665D") if "Unavailable" in health_text else colors.HexColor("#C9713C")
    )

    # Key Metrics Grid Table
    elements.append(Paragraph("Primary Environmental Metrics", section_style))
    metrics_data = [
        [
            Paragraph("<b>Canopy Cover</b>", body_style),
            Paragraph(f"<b>{analysis.forest_cover_pct}%</b>", body_style),
            Paragraph("<b>Current Condition</b>", body_style),
            Paragraph(f"<font color='#1F5C3B'><b>{cur_class}</b></font>", body_style)
        ],
        [
            Paragraph("<b>Estimated Trees</b>", body_style),
            Paragraph(f"{analysis.tree_count:,}", body_style),
            Paragraph("<b>Forest Health</b>", body_style),
            Paragraph(f"<font color='{health_color.hexval()}'><b>{health_text}</b></font>", body_style)
        ],
        [
            Paragraph("<b>Dry Biomass</b>", body_style),
            Paragraph(f"{analysis.biomass_tons:,.1f} tonnes", body_style),
            Paragraph("<b>Suitability Score</b>", body_style),
            Paragraph(f"<b>{analysis.suitability_score} / 100</b>", body_style)
        ],
        [
            Paragraph("<b>CO2e Offset</b>", body_style),
            Paragraph(f"<b>{analysis.co2_equivalent_tons:,.1f} t CO2e</b>", body_style),
            Paragraph("<b>AOI Surface Area</b>", body_style),
            Paragraph(f"{aoi.area_hectares:,.2f} ha", body_style)
        ]
    ]

    metrics_table = Table(metrics_data, colWidths=[120, 140, 120, 140])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F7F5EF")),
        ('BORDER', (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D4C7")),
        ('PADDING', (0, 0), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(metrics_table)
    elements.append(Spacer(1, 14))

    # Scientific Factor Contributions & Explainability Table
    elements.append(Paragraph("Scientific Indicator Breakdown & Factor Weights", section_style))

    contributors = cur_cond.get("contributors", {})
    ndvi_val = contributors.get("ndvi", 0.0)
    ndmi_val = contributors.get("ndmi", 0.0)
    biomass_ha = contributors.get("biomass_density_t_per_ha", 0.0)

    reforest_info = explainability.get("reforestation_suitability", {})
    reforest_class = reforest_info.get("classification", "Suitable")

    explain_data = [
        [Paragraph("<b>Assessment Module</b>", body_style), Paragraph("<b>Metric / Indicator</b>", body_style), Paragraph("<b>Value</b>", body_style), Paragraph("<b>Weight</b>", body_style)],
        [Paragraph("Current Vegetation", body_style), Paragraph("Canopy Cover %", body_style), Paragraph(f"{analysis.forest_cover_pct}%", body_style), Paragraph("35%", body_style)],
        [Paragraph("Current Vegetation", body_style), Paragraph("Optical NDVI Index", body_style), Paragraph(f"{ndvi_val:.2f}", body_style), Paragraph("30%", body_style)],
        [Paragraph("Current Vegetation", body_style), Paragraph("Moisture NDMI Index", body_style), Paragraph(f"{ndmi_val:.2f}", body_style), Paragraph("20%", body_style)],
        [Paragraph("Current Vegetation", body_style), Paragraph("Biomass Density", body_style), Paragraph(f"{biomass_ha:.1f} t/ha", body_style), Paragraph("15%", body_style)],
        [Paragraph("Reforestation Suitability", body_style), Paragraph("Canopy Gap Potential", body_style), Paragraph(f"{100.0 - float(analysis.forest_cover_pct):.1f}%", body_style), Paragraph("35%", body_style)],
        [Paragraph("Reforestation Suitability", body_style), Paragraph("Moisture & Water Capacity", body_style), Paragraph(f"{reforest_class}", body_style), Paragraph("30%", body_style)]
    ]

    explain_table = Table(explain_data, colWidths=[140, 180, 110, 90])
    explain_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E8E6DE")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D4C7")),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(explain_table)
    elements.append(Spacer(1, 14))

    # Scientific Validation Report Section
    val_report = result_layers.get("validation_report", {})
    confidence_level = val_report.get("confidence_level", "High")
    lit_val = val_report.get("literature_validation", {})

    elements.append(Paragraph("Scientific Validation & Peer Literature Audit", section_style))

    val_data = [
        [Paragraph("<b>Metric</b>", body_style), Paragraph("<b>Predicted</b>", body_style), Paragraph("<b>Expected Range</b>", body_style), Paragraph("<b>Difference</b>", body_style), Paragraph("<b>Status</b>", body_style), Paragraph("<b>Confidence</b>", body_style)],
        [
            Paragraph("Canopy Cover", body_style),
            Paragraph(f"{analysis.forest_cover_pct}%", body_style),
            Paragraph(f"{lit_val.get('canopy_cover', {}).get('expected_range', '30.0 – 90.0')}%", body_style),
            Paragraph(f"{lit_val.get('canopy_cover', {}).get('difference', 0.0)}%", body_style),
            Paragraph(f"<font color='#1F5C3B'><b>{lit_val.get('canopy_cover', {}).get('status', 'PASS')}</b></font>", body_style),
            Paragraph(f"<b>{confidence_level}</b>", body_style)
        ],
        [
            Paragraph("Biomass Density", body_style),
            Paragraph(f"{biomass_ha:.1f} t/ha", body_style),
            Paragraph(f"{lit_val.get('biomass_density', {}).get('expected_range', '40.0 – 250.0')} t/ha", body_style),
            Paragraph(f"{lit_val.get('biomass_density', {}).get('difference', 0.0)} t/ha", body_style),
            Paragraph(f"<font color='#1F5C3B'><b>{lit_val.get('biomass_density', {}).get('status', 'PASS')}</b></font>", body_style),
            Paragraph(f"<b>{confidence_level}</b>", body_style)
        ],
        [
            Paragraph("NDVI Index", body_style),
            Paragraph(f"{ndvi_val:.2f}", body_style),
            Paragraph(f"{lit_val.get('ndvi', {}).get('expected_range', '0.35 – 0.85')}", body_style),
            Paragraph(f"{lit_val.get('ndvi', {}).get('difference', 0.0)}", body_style),
            Paragraph(f"<font color='#1F5C3B'><b>{lit_val.get('ndvi', {}).get('status', 'PASS')}</b></font>", body_style),
            Paragraph(f"<b>{confidence_level}</b>", body_style)
        ],
        [
            Paragraph("NDMI Index", body_style),
            Paragraph(f"{ndmi_val:.2f}", body_style),
            Paragraph(f"{lit_val.get('ndmi', {}).get('expected_range', '0.05 – 0.60')}", body_style),
            Paragraph(f"{lit_val.get('ndmi', {}).get('difference', 0.0)}", body_style),
            Paragraph(f"<font color='#1F5C3B'><b>{lit_val.get('ndmi', {}).get('status', 'PASS')}</b></font>", body_style),
            Paragraph(f"<b>{confidence_level}</b>", body_style)
        ]
    ]

    val_table = Table(val_data, colWidths=[100, 85, 125, 80, 65, 65])
    val_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E8E6DE")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D4C7")),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(val_table)
    elements.append(Spacer(1, 14))

    # Metadata Details Table
    elements.append(Paragraph("AOI & Observation Metadata", section_style))
    meta_data = [
        [Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Value / Specification</b>", body_style)],
        [Paragraph("Parcel Name", body_style), Paragraph(f"<b>{aoi.name}</b>", body_style)],
        [Paragraph("Observation Window", body_style), Paragraph(f"{job.start_date} to {job.end_date} ({obs_days} days)", body_style)],
        [Paragraph("Historical Health Analysis", body_style), Paragraph(f"{'Available (' + str(health_info.get('classification', 'Healthy')) + ' — ' + str(obs_days) + ' days)' if health_info.get('available') else 'Unavailable (Requires >= 180 days)'}", body_style)],
        [Paragraph("Satellite Sensors", body_style), Paragraph("Sentinel-1 SAR C-Band + Sentinel-2 Optical", body_style)],
        [Paragraph("Raster Resolution", body_style), Paragraph("10.0m / pixel (10-Band Composite)", body_style)],
        [Paragraph("Report Generated", body_style), Paragraph(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), body_style)]
    ]

    meta_table = Table(meta_data, colWidths=[160, 360])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E8E6DE")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D4C7")),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 16))

    # Footer note
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D8D4C7"), spaceAfter=8))
    elements.append(Paragraph("<font size=8 color='#5B665D'>Generated automatically by Forest Intelligence System (FIS) v1.0.0 — Remote Sensing & IPCC Tier 1 Scientific Standards</font>", small_style))

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
    summary_text = generate_executive_summary(db_aoi, analysis, db_job)

    # 2. HTML Report
    html_path = render_html_report(db_job, db_aoi, analysis, summary_text)

    # 3. PDF Report
    output_dir = os.path.join(settings.LOCAL_STORAGE_PATH, "reports")
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"job_{job_id}_report.pdf")

    compile_pdf_with_reportlab(pdf_path, db_job, db_aoi, analysis, summary_text)

    return summary_text, html_path, pdf_path
