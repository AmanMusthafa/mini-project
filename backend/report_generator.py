"""
Real Report Generation Service
Generates live PDF executive accident safety audits and CSV exports.
"""
import io
import csv
import json
import sqlite3
from pathlib import Path
from backend.config import Config

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_pdf_report(db_conn, area_filter="", year_filter=""):
    """Generate a formatted PDF Road Safety Audit Report."""
    c = db_conn.cursor()
    
    # 1. Fetch filtered stats
    where_clauses = []
    params = []
    if area_filter:
        where_clauses.append("area = ?")
        params.append(area_filter)
    if year_filter:
        where_clauses.append("year = ?")
        params.append(int(year_filter))
        
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    
    total = c.execute(f"SELECT COUNT(*) FROM accidents {where_sql}", params).fetchone()[0]
    fatal = c.execute(f"SELECT COUNT(*) FROM accidents {where_sql} {'AND' if where_sql else 'WHERE'} severity='fatal'", params).fetchone()[0]
    major = c.execute(f"SELECT COUNT(*) FROM accidents {where_sql} {'AND' if where_sql else 'WHERE'} severity='major'", params).fetchone()[0]
    minor = c.execute(f"SELECT COUNT(*) FROM accidents {where_sql} {'AND' if where_sql else 'WHERE'} severity='minor'", params).fetchone()[0]
    casualties = c.execute(f"SELECT SUM(casualties) FROM accidents {where_sql}", params).fetchone()[0] or 0
    
    # Top hotspots
    hotspots_sql = f"""
        SELECT area, road_name, COUNT(*) as total_acc,
               SUM(CASE WHEN severity='fatal' THEN 1 ELSE 0 END) as fatal_cnt,
               SUM(CASE WHEN severity='major' THEN 1 ELSE 0 END) as major_cnt
        FROM accidents
        {where_sql}
        GROUP BY area, road_name
        ORDER BY total_acc DESC
        LIMIT 6
    """
    hotspots = c.execute(hotspots_sql, params).fetchall()
    
    # Load model metrics if available
    model_card_path = Path(Config.ML_MODELS_DIR) / "model_card.json"
    model_info = {}
    if model_card_path.exists():
        with open(model_card_path, "r") as f:
            model_info = json.load(f)
            
    # Build PDF Document
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=40, bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'],
        fontSize=20, leading=24, textColor=colors.HexColor('#0F172A')
    )
    subtitle_style = ParagraphStyle(
        'DocSub', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#64748B')
    )
    h2_style = ParagraphStyle(
        'H2', parent=styles['Heading2'],
        fontSize=13, leading=16, textColor=colors.HexColor('#1E293B'),
        spaceBefore=14, spaceAfter=6
    )
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'],
        fontSize=9, leading=13, textColor=colors.HexColor('#334155')
    )
    disclaimer_style = ParagraphStyle(
        'Disclaimer', parent=styles['Normal'],
        fontSize=8, leading=11, textColor=colors.HexColor('#DC2626')
    )

    story = []
    
    # Title & Header
    story.append(Paragraph("Kochi Road Safety & Traffic Audit Report", title_style))
    story.append(Paragraph("AI-Powered Accident Analytics and Severity Monitoring System", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#17B26A'), spaceBefore=8, spaceAfter=12))
    
    # Disclaimer Box
    story.append(Paragraph("<b>DATA PROVENANCE & LIMITATION NOTICE:</b>", disclaimer_style))
    story.append(Paragraph(
        "Statistics in this report are based on synthetic Kochi road accident data generated for research and demonstration. "
        "Not validated for physical emergency dispatch or legal liability determinations.",
        disclaimer_style
    ))
    story.append(Spacer(1, 12))
    
    # Summary Table
    story.append(Paragraph("Executive Incident Summary", h2_style))
    summary_data = [
        ["Total Recorded Crashes", f"{total:,}", "Total Casualties", f"{casualties:,}"],
        ["Fatal Collisions", f"{fatal:,} ({fatal/max(total,1)*100:.1f}%)", "Major Injuries", f"{major:,} ({major/max(total,1)*100:.1f}%)"],
        ["Minor Incidents", f"{minor:,} ({minor/max(total,1)*100:.1f}%)", "Scope Filter", f"Area: {area_filter or 'All'}, Year: {year_filter or 'All'}"]
    ]
    sum_table = Table(summary_data, colWidths=[140, 125, 140, 125])
    sum_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#1E293B')),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 14))
    
    # Top Critical Hotspots Table
    story.append(Paragraph("Top Critical Road Segments & Hotspots", h2_style))
    hs_rows = [["Area", "Corridor / Junction", "Total Crashes", "Fatal", "Major"]]
    for r in hotspots:
        hs_rows.append([r[0], r[1], str(r[2]), str(r[3]), str(r[4])])
    if len(hs_rows) == 1:
        hs_rows.append(["No records matching filter", "-", "-", "-", "-"])
        
    hs_table = Table(hs_rows, colWidths=[100, 210, 80, 70, 70])
    hs_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('ALIGN', (2,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(hs_table)
    story.append(Spacer(1, 14))
    
    # Machine Learning Severity Model Card Summary
    if model_info:
        story.append(Paragraph("Verified Machine Learning Model Performance", h2_style))
        m_metrics = model_info.get("metrics", {})
        ml_data = [
            ["Model Architecture", model_info.get("model_name", "XGBoost Classifier"), "Hold-out Accuracy", f"{m_metrics.get('test_accuracy', 0)*100:.1f}%"],
            ["Macro-F1 Score", f"{m_metrics.get('test_macro_f1', 0):.4f}", "5-Fold CV F1", f"{m_metrics.get('cv_5fold_macro_f1', 'N/A')}"],
            ["Majority Class Baseline", f"{m_metrics.get('majority_baseline_accuracy', 0)*100:.1f}%", "Explainability", "TreeSHAP Local Attribution"]
        ]
        ml_table = Table(ml_data, colWidths=[140, 125, 140, 125])
        ml_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8.5),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(ml_table)
        
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def stream_csv_export(db_conn, filters=None):
    """Generate in-memory CSV export of filtered accident records."""
    filters = filters or {}
    c = db_conn.cursor()
    
    where_clauses = []
    params = []
    if filters.get("year"):
        where_clauses.append("year = ?")
        params.append(int(filters["year"]))
    if filters.get("severity"):
        where_clauses.append("severity = ?")
        params.append(filters["severity"].lower())
    if filters.get("area"):
        where_clauses.append("area = ?")
        params.append(filters["area"])
        
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    
    cols = [
        "accident_uid", "occurred_at", "year", "area", "road_name", "road_type",
        "lanes", "traffic_signal", "latitude", "longitude", "weather", "visibility",
        "traffic_density", "cause", "severity", "vehicles_involved", "casualties", "data_source"
    ]
    query = f"SELECT {', '.join(cols)} FROM accidents {where_sql} ORDER BY occurred_at DESC LIMIT 5000"
    rows = c.execute(query, params).fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(cols)
    for r in rows:
        writer.writerow(list(r))
        
    output.seek(0)
    return output.getvalue()
