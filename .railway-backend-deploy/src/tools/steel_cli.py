"""
Steel CLI Wrapper - Use Steel browser via CLI subprocess
Direct CLI calls - works with installed Steel CLI
"""

import subprocess
import json
import logging
from typing import Dict, Any
from pathlib import Path
import tempfile
import re

logger = logging.getLogger(__name__)


class SteelCLI:
    """Wrapper for Steel CLI commands"""
    
    def __init__(self):
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
    
    async def analyze_website(self, website: str, business_name: str) -> Dict[str, Any]:
        """
        Analyze website using Steel CLI
        
        Creates a temporary Steel script and runs it via CLI
        """
        
        if not website:
            return {"status": "no_website"}
        
        try:
            logger.info(f"[STEEL CLI] Analyzing {website}")
            
            # Create a temporary Steel script
            script_content = f"""
// Steel automation script
const {{ chromium }} = require('playwright');

(async () => {{
    const browser = await chromium.launch();
    const page = await browser.newPage();
    
    try {{
        // Navigate to website
        await page.goto('{website}', {{ waitUntil: 'networkidle', timeout: 30000 }});
        
        // Wait a bit for dynamic content
        await page.waitForTimeout(2000);
        
        // Get page content
        const html = await page.content();
        
        // Extract signals
        const signals = {{
            has_booking_system: false,
            has_whatsapp: false,
            has_lead_form: false,
            has_click_to_call: false,
            has_chat_widget: false,
            emails: [],
            phones: []
        }};
        
        // Check for booking systems
        const bookingKeywords = ['book appointment', 'book now', 'schedule', 'calendly', 'practo'];
        for (const keyword of bookingKeywords) {{
            if (html.toLowerCase().includes(keyword)) {{
                signals.has_booking_system = true;
                break;
            }}
        }}
        
        // Check for WhatsApp
        if (html.toLowerCase().includes('whatsapp') || html.toLowerCase().includes('wa.me')) {{
            signals.has_whatsapp = true;
        }}
        
        // Check for forms
        if (html.includes('<form') || html.toLowerCase().includes('contact form')) {{
            signals.has_lead_form = true;
        }}
        
        // Check for click to call
        if (html.includes('tel:') || html.toLowerCase().includes('call now')) {{
            signals.has_click_to_call = true;
        }}
        
        // Check for chat widgets
        const chatKeywords = ['tawk.to', 'intercom', 'drift', 'crisp', 'livechat'];
        for (const keyword of chatKeywords) {{
            if (html.toLowerCase().includes(keyword)) {{
                signals.has_chat_widget = true;
                break;
            }}
        }}
        
        // Extract emails
        const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}/g;
        const emails = html.match(emailRegex) || [];
        signals.emails = [...new Set(emails)].slice(0, 5);
        
        // Extract phones
        const phoneRegex = /\\+91[\\s-]?\\d{{10}}|\\d{{10}}/g;
        const phones = html.match(phoneRegex) || [];
        signals.phones = [...new Set(phones)].slice(0, 3);
        
        // Output results
        console.log(JSON.stringify(signals));
        
    }} catch (error) {{
        console.error('Error:', error.message);
        process.exit(1);
    }} finally {{
        await browser.close();
    }}
}})();
"""
            
            # Write script to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(script_content)
                script_path = f.name
            
            try:
                # Run Steel CLI with the script
                result = subprocess.run(
                    ['steel', 'run', script_path],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    # Parse JSON output
                    output = result.stdout.strip()
                    # Find JSON in output
                    json_match = re.search(r'\{.*\}', output, re.DOTALL)
                    if json_match:
                        signals = json.loads(json_match.group())
                        signals["status"] = "steel_cli_success"
                        logger.info(f"[STEEL CLI] Success: {signals}")
                        return signals
                    else:
                        logger.warning(f"[STEEL CLI] No JSON in output: {output}")
                        return self._fallback_signals(website)
                else:
                    logger.error(f"[STEEL CLI] Error: {result.stderr}")
                    return self._fallback_signals(website)
                    
            finally:
                # Clean up temp file
                Path(script_path).unlink(missing_ok=True)
                
        except subprocess.TimeoutExpired:
            logger.error(f"[STEEL CLI] Timeout for {website}")
            return self._fallback_signals(website)
        except Exception as e:
            logger.error(f"[STEEL CLI] Error: {e}")
            return self._fallback_signals(website)
    
    def _fallback_signals(self, website: str) -> Dict[str, Any]:
        """Fallback when Steel CLI fails"""
        website_lower = website.lower()
        return {
            "status": "fallback",
            "has_booking_system": any(kw in website_lower for kw in ["practo", "calendly", "zocdoc", "booking"]),
            "has_whatsapp": "whatsapp" in website_lower or "wa.me" in website_lower,
            "has_lead_form": True,
            "has_click_to_call": True,
            "has_chat_widget": False,
            "emails": [],
            "phones": [],
            "booking_links": [],
            "social_links": {}
        }
