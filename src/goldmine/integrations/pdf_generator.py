"""
PDF PROOF DECK GENERATOR - Create irrefutable evidence.

Generates professional PDF proof decks showing:
- "You're losing $X,XXX/month" headline
- Mystery shopping evidence
- Competitor comparison
- Review evidence
- Clear call to action
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from io import BytesIO

logger = logging.getLogger(__name__)


class ProofDeckPDF:
    """
    Generate PDF proof decks for leads.
    
    Uses ReportLab for PDF generation (free, no API needed).
    """
    
    def __init__(self):
        """Initialize PDF generator."""
        self.reportlab_available = False
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            self.reportlab_available = True
            logger.info("✅ ReportLab available for PDF generation")
        except ImportError:
            logger.warning("ReportLab not installed. Run: pip install reportlab")
            
    def generate_proof_deck(
        self,
        lead: Dict[str, Any],
        monthly_loss: float,
        loss_breakdown: Dict[str, float] = None,
        mystery_shop_results: Dict[str, Any] = None,
        competitor_data: List[Dict[str, Any]] = None,
        review_evidence: List[Dict[str, Any]] = None,
        booking_url: str = None,
    ) -> bytes:
        """
        Generate a PDF proof deck.
        
        Args:
            lead: Lead data
            monthly_loss: Calculated monthly loss
            loss_breakdown: Breakdown by category
            mystery_shop_results: Mystery shopping evidence
            competitor_data: Competitor comparison
            review_evidence: Negative review quotes
            booking_url: Calendar booking URL
            
        Returns:
            PDF as bytes
        """
        if not self.reportlab_available:
            return self._generate_simple_pdf(lead, monthly_loss, booking_url)
            
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=28,
            textColor=colors.HexColor('#DC2626'),  # Red
            spaceAfter=20,
            alignment=1,  # Center
        )
        
        headline_style = ParagraphStyle(
            'Headline',
            parent=styles['Heading1'],
            fontSize=36,
            textColor=colors.HexColor('#DC2626'),
            spaceAfter=30,
            alignment=1,
        )
        
        subhead_style = ParagraphStyle(
            'Subhead',
            parent=styles['Heading2'],
            fontSize=18,
            textColor=colors.HexColor('#1F2937'),
            spaceBefore=20,
            spaceAfter=10,
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#374151'),
            spaceAfter=10,
        )
        
        business_name = lead.get("business_name", "Your Business")
        annual_loss = monthly_loss * 12
        
        # Build document
        story = []
        
        # Header
        story.append(Paragraph("REVENUE LEAK ANALYSIS", title_style))
        story.append(Paragraph(business_name, styles['Heading2']))
        story.append(Spacer(1, 20))
        
        # The Hook - Big red number
        story.append(Paragraph(
            f"You're Losing ${monthly_loss:,.0f}/Month",
            headline_style
        ))
        story.append(Paragraph(
            f"That's ${annual_loss:,.0f} per year walking out the door.",
            body_style
        ))
        story.append(Spacer(1, 30))
        
        # Loss Breakdown
        if loss_breakdown:
            story.append(Paragraph("Where You're Losing Money:", subhead_style))
            
            breakdown_data = [["Category", "Monthly Loss"]]
            for category, amount in loss_breakdown.items():
                breakdown_data.append([
                    category.replace("_", " ").title(),
                    f"${amount:,.0f}"
                ])
            breakdown_data.append(["TOTAL", f"${monthly_loss:,.0f}"])
            
            breakdown_table = Table(breakdown_data, colWidths=[4*inch, 2*inch])
            breakdown_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FEE2E2')),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
            ]))
            story.append(breakdown_table)
            story.append(Spacer(1, 30))
            
        # Mystery Shopping Evidence
        if mystery_shop_results:
            story.append(Paragraph("What We Found:", subhead_style))
            
            response_time = mystery_shop_results.get("form_response_time_hours")
            if response_time:
                if response_time > 24:
                    story.append(Paragraph(
                        f"⚠️ Contact form response time: {response_time:.0f} hours (industry standard: 5 minutes)",
                        body_style
                    ))
                else:
                    story.append(Paragraph(
                        f"✓ Contact form response time: {response_time:.1f} hours",
                        body_style
                    ))
                    
            if mystery_shop_results.get("phone_answered") == False:
                story.append(Paragraph(
                    "⚠️ Phone call went unanswered during business hours",
                    body_style
                ))
                
            story.append(Spacer(1, 20))
            
        # Competitor Comparison
        if competitor_data:
            story.append(Paragraph("How You Compare to Competitors:", subhead_style))
            
            comp_data = [["Feature", "You", "Top Competitor"]]
            for comp in competitor_data[:1]:  # Just show top competitor
                comp_data.append(["Online Booking", "❌ No", "✅ Yes" if comp.get("has_online_booking") else "❌ No"])
                comp_data.append(["Chat Widget", "❌ No", "✅ Yes" if comp.get("has_chat_widget") else "❌ No"])
                comp_data.append(["Google Rating", lead.get("rating", "N/A"), comp.get("google_rating", "N/A")])
                
            comp_table = Table(comp_data, colWidths=[2.5*inch, 1.75*inch, 1.75*inch])
            comp_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
            ]))
            story.append(comp_table)
            story.append(Spacer(1, 20))
            
        # Review Evidence
        if review_evidence:
            story.append(Paragraph("What Your Customers Are Saying:", subhead_style))
            
            for review in review_evidence[:3]:
                quote = review.get("quote", review.get("review_text", ""))[:200]
                story.append(Paragraph(
                    f'"{quote}..." - {review.get("source", "Google")} Review',
                    ParagraphStyle(
                        'Quote',
                        parent=body_style,
                        leftIndent=20,
                        rightIndent=20,
                        textColor=colors.HexColor('#6B7280'),
                        fontName='Helvetica-Oblique',
                    )
                ))
            story.append(Spacer(1, 20))
            
        # Call to Action
        story.append(Spacer(1, 30))
        story.append(Paragraph("Let's Fix This", subhead_style))
        story.append(Paragraph(
            "I can show you exactly how to capture these missed opportunities. "
            "Most businesses see results within 30 days.",
            body_style
        ))
        
        if booking_url:
            story.append(Spacer(1, 10))
            story.append(Paragraph(
                f"<b>Book a 15-minute call:</b> {booking_url}",
                ParagraphStyle(
                    'CTA',
                    parent=body_style,
                    fontSize=14,
                    textColor=colors.HexColor('#2563EB'),
                )
            ))
            
        # Footer
        story.append(Spacer(1, 40))
        story.append(Paragraph(
            f"Analysis generated on {datetime.now().strftime('%B %d, %Y')}",
            ParagraphStyle(
                'Footer',
                parent=body_style,
                fontSize=10,
                textColor=colors.HexColor('#9CA3AF'),
                alignment=1,
            )
        ))
        
        # Build PDF
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        logger.info(f"📄 PDF proof deck generated for {business_name} ({len(pdf_bytes)} bytes)")
        return pdf_bytes
        
    def _generate_simple_pdf(
        self,
        lead: Dict[str, Any],
        monthly_loss: float,
        booking_url: str = None,
    ) -> bytes:
        """
        Generate a simple text-based PDF without ReportLab.
        Falls back to basic formatting.
        """
        # Simple text content
        business_name = lead.get("business_name", "Your Business")
        annual_loss = monthly_loss * 12
        
        content = f"""
REVENUE LEAK ANALYSIS
{business_name}
{'=' * 50}

YOU'RE LOSING ${monthly_loss:,.0f}/MONTH
That's ${annual_loss:,.0f} per year walking out the door.

{'=' * 50}

WHAT WE FOUND:
- Slow response times to inquiries
- Missing online booking capability
- Competitors are capturing your customers

{'=' * 50}

LET'S FIX THIS

I can show you exactly how to capture these missed opportunities.
Most businesses see results within 30 days.

{f"Book a call: {booking_url}" if booking_url else "Reply to schedule a call."}

{'=' * 50}
Analysis generated on {datetime.now().strftime('%B %d, %Y')}
"""
        
        # Return as bytes (basic text file, not real PDF)
        return content.encode('utf-8')
        
    def save_proof_deck(
        self,
        lead: Dict[str, Any],
        monthly_loss: float,
        output_path: str = None,
        **kwargs,
    ) -> str:
        """
        Generate and save a proof deck to file.
        
        Args:
            lead: Lead data
            monthly_loss: Monthly loss amount
            output_path: Where to save (default: ./proof_decks/)
            **kwargs: Additional args for generate_proof_deck
            
        Returns:
            Path to saved file
        """
        pdf_bytes = self.generate_proof_deck(lead, monthly_loss, **kwargs)
        
        business_name = lead.get("business_name", "business").replace(" ", "_")
        filename = f"{business_name}_proof_deck_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        if output_path is None:
            output_path = os.path.join("proof_decks", filename)
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path) or "proof_decks", exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)
            
        logger.info(f"📄 Proof deck saved to {output_path}")
        return output_path


# Convenience function
def generate_proof_pdf(
    lead: Dict[str, Any],
    monthly_loss: float,
    booking_url: str = None,
) -> bytes:
    """Generate a proof deck PDF."""
    generator = ProofDeckPDF()
    return generator.generate_proof_deck(
        lead=lead,
        monthly_loss=monthly_loss,
        booking_url=booking_url,
    )
