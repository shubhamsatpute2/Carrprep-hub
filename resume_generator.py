"""Module for generating resume documents in different formats"""
import json
from io import BytesIO
from typing import Optional, List, Dict, Any
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

def safe_json_parse(json_str):
    """Helper function to safely parse JSON or return empty list"""
    if not json_str:
        return []
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return [json_str] if json_str else []

def generate_resume_docx(resume_data: Dict[str, Any]) -> BytesIO:
    """Generate a resume in Word (.docx) format"""
    doc = Document()
    
    # Set document margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
    
    # Header with name and contact info
    name = resume_data.get('name', 'Your Name')
    heading = doc.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = heading.add_run(name)
    name_run.font.size = Pt(16)
    name_run.font.bold = True
    
    # Contact information
    contact = doc.add_paragraph()
    contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
    contact_parts = []
    
    if resume_data.get('email'):
        contact_parts.append(resume_data['email'])
    if resume_data.get('phone'):
        contact_parts.append(resume_data['phone'])
    if resume_data.get('linkedin'):
        contact_parts.append(f"LinkedIn: {resume_data['linkedin']}")
    if resume_data.get('github'):
        contact_parts.append(f"GitHub: {resume_data['github']}")
    if resume_data.get('portfolio'):
        contact_parts.append(f"Portfolio: {resume_data['portfolio']}")
    
    contact.add_run(" | ".join(contact_parts))
    contact.runs[0].font.size = Pt(10)
    
    if resume_data.get('address'):
        address = doc.add_paragraph(resume_data['address'])
        address.alignment = WD_ALIGN_PARAGRAPH.CENTER
        address.runs[0].font.size = Pt(9)
    
    doc.add_paragraph()  # Spacing
    
    # Professional Summary
    if resume_data.get('summary'):
        doc.add_heading('Professional Summary', level=2)
        doc.add_paragraph(resume_data['summary'])
    
    # Skills
    skills = resume_data.get('skills', [])
    if skills:
        doc.add_heading('Skills', level=2)
        if isinstance(skills, list):
            skills_text = ", ".join(skills)
        else:
            skills_text = skills
        doc.add_paragraph(skills_text)
    
    # Education
    education = safe_json_parse(resume_data.get('education'))
    if education:
        doc.add_heading('Education', level=2)
        for edu in education:
            if isinstance(edu, dict):
                edu_text = edu.get('degree', '') or ''
                if edu.get('school'):
                    edu_text += f" - {edu['school']}"
                if edu.get('year'):
                    edu_text += f" ({edu['year']})"
                if edu_text:
                    doc.add_paragraph(edu_text, style='List Bullet')
            else:
                doc.add_paragraph(str(edu), style='List Bullet')
    
    # Experience
    experience = safe_json_parse(resume_data.get('experience'))
    if experience:
        doc.add_heading('Experience', level=2)
        for exp in experience:
            if isinstance(exp, dict):
                company = exp.get('company', '')
                role = exp.get('role', '')
                years = exp.get('years', '')
                description = exp.get('description', '')
                
                exp_title = f"{role}"
                if company:
                    exp_title += f" - {company}"
                if years:
                    exp_title += f" ({years})"
                
                if exp_title:
                    doc.add_paragraph(exp_title, style='List Bullet')
                if description:
                    doc.add_paragraph(description, style='List Bullet 2')
            else:
                doc.add_paragraph(str(exp), style='List Bullet')
    
    # Projects
    projects = safe_json_parse(resume_data.get('projects'))
    if projects:
        doc.add_heading('Projects', level=2)
        for proj in projects:
            if isinstance(proj, dict):
                title = proj.get('title', '') or ''
                description = proj.get('description', '')
                if title:
                    doc.add_paragraph(title, style='List Bullet')
                if description:
                    doc.add_paragraph(description, style='List Bullet 2')
            else:
                doc.add_paragraph(str(proj), style='List Bullet')
    
    # Certifications
    certs = safe_json_parse(resume_data.get('certifications'))
    if certs:
        doc.add_heading('Certifications', level=2)
        for cert in certs:
            if isinstance(cert, dict):
                cert_name = cert.get('name', '') or ''
                issuer = cert.get('issuer', '')
                if cert_name:
                    cert_text = cert_name
                    if issuer:
                        cert_text += f" - {issuer}"
                    doc.add_paragraph(cert_text, style='List Bullet')
            else:
                doc.add_paragraph(str(cert), style='List Bullet')
    
    # Awards
    awards = safe_json_parse(resume_data.get('awards'))
    if awards:
        doc.add_heading('Awards & Achievements', level=2)
        for award in awards:
            doc.add_paragraph(str(award), style='List Bullet')
    
    # Publications
    pubs = safe_json_parse(resume_data.get('publications'))
    if pubs:
        doc.add_heading('Publications', level=2)
        for pub in pubs:
            doc.add_paragraph(str(pub), style='List Bullet')
    
    # Languages
    languages = resume_data.get('languages')
    if languages:
        doc.add_heading('Languages', level=2)
        if isinstance(languages, list):
            langs_text = ", ".join(languages)
        else:
            langs_text = str(languages)
        doc.add_paragraph(langs_text)
    
    # Save to BytesIO
    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output


def generate_resume_pdf(resume_data: Dict[str, Any]) -> BytesIO:
    """Generate a resume in PDF format"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        
        output = BytesIO()
        doc = SimpleDocTemplate(output, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # Create custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#000000'),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=6,
            spaceBefore=6,
            fontName='Helvetica-Bold',
            borderColor=colors.grey,
            borderWidth=0.5,
            borderPadding=4
        )
        
        # Title
        name = resume_data.get('name', 'Your Name')
        story.append(Paragraph(name, title_style))
        
        # Contact Info
        contact_parts = []
        if resume_data.get('email'):
            contact_parts.append(resume_data['email'])
        if resume_data.get('phone'):
            contact_parts.append(resume_data['phone'])
        if resume_data.get('linkedin'):
            contact_parts.append(f"LinkedIn: {resume_data['linkedin']}")
        if resume_data.get('github'):
            contact_parts.append(f"GitHub: {resume_data['github']}")
        
        if contact_parts:
            contact_text = " | ".join(contact_parts)
            contact_para = ParagraphStyle('Contact', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)
            story.append(Paragraph(contact_text, contact_para))
        
        if resume_data.get('address'):
            addr_style = ParagraphStyle('Address', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)
            story.append(Paragraph(resume_data['address'], addr_style))
        
        story.append(Spacer(1, 0.1*inch))
        
        # Professional Summary
        if resume_data.get('summary'):
            story.append(Paragraph('Professional Summary', heading_style))
            story.append(Paragraph(resume_data['summary'], styles['Normal']))
            story.append(Spacer(1, 0.1*inch))
        
        # Skills
        skills = resume_data.get('skills', [])
        if skills:
            story.append(Paragraph('Skills', heading_style))
            if isinstance(skills, list):
                skills_text = ", ".join(skills)
            else:
                skills_text = str(skills)
            story.append(Paragraph(skills_text, styles['Normal']))
            story.append(Spacer(1, 0.1*inch))
        
        # Education
        education = safe_json_parse(resume_data.get('education'))
        if education:
            story.append(Paragraph('Education', heading_style))
            for edu in education:
                if isinstance(edu, dict):
                    edu_text = edu.get('degree', '') or ''
                    if edu.get('school'):
                        edu_text += f" - {edu['school']}"
                    if edu.get('year'):
                        edu_text += f" ({edu['year']})"
                    if edu_text:
                        story.append(Paragraph(f"• {edu_text}", styles['Normal']))
                else:
                    story.append(Paragraph(f"• {str(edu)}", styles['Normal']))
            story.append(Spacer(1, 0.1*inch))
        
        # Experience
        experience = safe_json_parse(resume_data.get('experience'))
        if experience:
            story.append(Paragraph('Experience', heading_style))
            for exp in experience:
                if isinstance(exp, dict):
                    company = exp.get('company', '')
                    role = exp.get('role', '')
                    years = exp.get('years', '')
                    
                    exp_title = role
                    if company:
                        exp_title += f" - {company}"
                    if years:
                        exp_title += f" ({years})"
                    
                    if exp_title:
                        story.append(Paragraph(f"• {exp_title}", styles['Normal']))
                    if exp.get('description'):
                        story.append(Paragraph(f"  {exp['description']}", styles['Normal']))
                else:
                    story.append(Paragraph(f"• {str(exp)}", styles['Normal']))
            story.append(Spacer(1, 0.1*inch))
        
        doc.build(story)
        output.seek(0)
        return output
        
    except ImportError:
        # Fallback: return docx if reportlab not available
        return generate_resume_docx(resume_data)
