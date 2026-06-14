import os
import urllib.request
import ssl
from fpdf import FPDF

# Avoid SSL verification issues on some Windows systems
ssl._create_default_https_context = ssl._create_unverified_context

# Download fonts to support both Spanish accents and IPA phonetic symbols
def download_fonts():
    fonts = {
        "DejaVuSans.ttf": "https://raw.githubusercontent.com/prawnpdf/prawn/master/data/fonts/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf": "https://raw.githubusercontent.com/prawnpdf/prawn/master/data/fonts/DejaVuSans-Bold.ttf",
    }
    for name, url in fonts.items():
        if not os.path.exists(name):
            print(f"Downloading {name} from {url}...")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(name, 'wb') as out_file:
                out_file.write(response.read())

class ClinicalReportPDF(FPDF):
    def header(self):
        # Draw a beautiful top slate bar
        self.set_fill_color(30, 41, 59)  # #1e293b (slate-800)
        self.rect(0, 0, 210, 8, "F")
        
        self.set_font("DejaVuSans", "", 8)
        self.set_text_color(100, 116, 139)  # #64748b (slate-500)
        self.set_y(12)
        self.cell(0, 5, "Propuestas de Evolución Clínica — cribado fonológico pediátrico", align="R")
        self.ln(6)
        
    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVuSans", "", 8)
        self.set_text_color(100, 116, 139)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")

def draw_blockquote(pdf, text):
    pdf.set_fill_color(248, 250, 252)  # #f8fafc (slate-50)
    pdf.set_text_color(71, 85, 105)  # #475569 (slate-600)
    
    pdf.set_left_margin(28)
    pdf.set_right_margin(25)
    pdf.set_x(28)
    
    y_start = pdf.get_y()
    pdf.multi_cell(w=157, h=5.5, text=text, border=0, fill=True, markdown=True)
    y_end = pdf.get_y()
    
    pdf.set_draw_color(59, 130, 246)  # Blue (#3b82f6)
    pdf.set_line_width(1.5)
    pdf.line(26, y_start, 26, y_end)
    
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)
    pdf.set_text_color(51, 65, 85)  # Restore body color
    pdf.ln(4)

def draw_table(pdf, headers, rows):
    col1_width = 45
    col2_width = 125
    x_start = 20
    
    # Table Header Row
    pdf.set_font("DejaVuSans", "B", 10)
    pdf.set_fill_color(30, 41, 59)  # Deep slate #1e293b
    pdf.set_text_color(255, 255, 255)  # White
    
    pdf.cell(col1_width, 10, headers[0], border=1, fill=True, align="C")
    pdf.cell(col2_width, 10, headers[1], border=1, fill=True, align="C")
    pdf.ln()
    
    pdf.set_font("DejaVuSans", "", 9.5)
    pdf.set_text_color(51, 65, 85)  # Slate-700
    
    for i, row in enumerate(rows):
        priority_raw, action = row[0], row[1]
        
        # Clean priority text and detect color
        color = None
        if "🟢" in priority_raw or "Rápida" in priority_raw:
            color = (34, 197, 94)  # Green (#22c55e)
            priority_text = priority_raw.replace("🟢", "").strip()
        elif "🟡" in priority_raw or "Media" in priority_raw:
            color = (234, 179, 8)  # Yellow (#eab308)
            priority_text = priority_raw.replace("🟡", "").strip()
        elif "🔴" in priority_raw or "Mayor" in priority_raw:
            color = (239, 68, 68)  # Red (#ef4444)
            priority_text = priority_raw.replace("🔴", "").strip()
        else:
            priority_text = priority_raw.strip()
            
        bg_color = (248, 250, 252) if i % 2 == 1 else (255, 255, 255)
        
        # Estimate height for page breaks
        lines = pdf.multi_cell(col2_width - 6, 5.5, action, dry_run=True, output="LINES")
        num_lines = len(lines)
        est_height = max(10, num_lines * 5.5 + 4)
        
        if pdf.get_y() + est_height > 270:
            pdf.add_page()
            # Redraw header
            pdf.set_font("DejaVuSans", "B", 10)
            pdf.set_fill_color(30, 41, 59)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(col1_width, 10, headers[0], border=1, fill=True, align="C")
            pdf.cell(col2_width, 10, headers[1], border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_font("DejaVuSans", "", 9.5)
            pdf.set_text_color(51, 65, 85)
            
        y_start = pdf.get_y()
        row_height = est_height
        
        # Draw background and borders first
        pdf.set_fill_color(*bg_color)
        pdf.set_draw_color(203, 213, 225)
        pdf.rect(x_start, y_start, col1_width, row_height, "F")
        pdf.rect(x_start + col1_width, y_start, col2_width, row_height, "F")
        pdf.rect(x_start, y_start, col1_width, row_height, "D")
        pdf.rect(x_start + col1_width, y_start, col2_width, row_height, "D")
        
        # Draw Col 1 (Priority)
        if color:
            pdf.set_fill_color(*color)
            circle_y = y_start + (row_height - 3.5) / 2
            pdf.ellipse(x_start + 4, circle_y, 3.5, 3.5, "F")
            pdf.set_xy(x_start + 9, y_start)
            pdf.set_font("DejaVuSans", "B", 9)
            pdf.cell(col1_width - 9, row_height, priority_text, align="L")
        else:
            pdf.set_xy(x_start, y_start)
            pdf.set_font("DejaVuSans", "", 9)
            pdf.cell(col1_width, row_height, priority_text, align="C")
            
        # Draw Col 2 (Action)
        pdf.set_font("DejaVuSans", "", 9)
        pdf.set_xy(x_start + col1_width + 3, y_start + (row_height - (num_lines * 5.5)) / 2)
        pdf.set_left_margin(x_start + col1_width + 3)
        pdf.set_right_margin(23)
        pdf.multi_cell(col2_width - 6, 5.5, action, border=0, fill=False, align="L", markdown=True)
        
        # Restore margins
        pdf.set_left_margin(20)
        pdf.set_right_margin(20)
        pdf.set_xy(x_start, y_start + row_height)
    
    pdf.ln(4)

def main():
    download_fonts()
    
    pdf = ClinicalReportPDF()
    pdf.add_font("DejaVuSans", "", "DejaVuSans.ttf")
    pdf.add_font("DejaVuSans", "B", "DejaVuSans-Bold.ttf")
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    
    # Custom Title Block
    pdf.set_font("DejaVuSans", "B", 18)
    pdf.set_text_color(30, 41, 59)  # Deep slate
    pdf.cell(0, 10, "Análisis Clínico Especializado", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVuSans", "B", 13)
    pdf.set_text_color(100, 116, 139)  # Slate-500
    pdf.cell(0, 8, "Propuestas de Evolución Clínica para el Cribado Fonológico", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    # Accent line
    pdf.set_draw_color(59, 130, 246)  # Blue accent
    pdf.set_line_width(1.2)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(6)
    
    # Read markdown file
    md_path = "docs/mejoras_clinicas.md"
    if not os.path.exists(md_path):
        print(f"Error: {md_path} not found.")
        return
        
    with open(md_path, "r", encoding="utf-8") as f:
        lines = [line.rstrip('\n') for line in f]
        
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        
        # Skip empty lines
        if not line.strip():
            i += 1
            continue
            
        # Skip main title (already printed as styled block)
        if line.startswith("# "):
            i += 1
            continue
            
        # Heading 2
        elif line.startswith("## "):
            heading = line[3:].strip()
            pdf.set_font("DejaVuSans", "B", 12)
            pdf.set_text_color(30, 41, 59)
            pdf.ln(4)
            pdf.multi_cell(0, 6, heading, markdown=True)
            pdf.ln(2)
            i += 1
            
        # Heading 3
        elif line.startswith("### "):
            heading = line[4:].strip()
            pdf.set_font("DejaVuSans", "B", 11)
            pdf.set_text_color(59, 130, 246)  # Accent blue
            pdf.ln(3)
            pdf.multi_cell(0, 6, heading, markdown=True)
            pdf.ln(2)
            i += 1
            
        # Blockquote
        elif line.startswith("> "):
            bq_lines = []
            while i < n and lines[i].startswith("> "):
                line_content = lines[i][1:].strip()
                bq_lines.append(line_content)
                i += 1
            bq_text = " ".join(bq_lines)
            draw_blockquote(pdf, bq_text)
            
        # List Item
        elif line.startswith("- "):
            list_text = line[2:].strip()
            pdf.set_left_margin(25)
            pdf.set_x(25)
            # Draw small bullet circle
            pdf.ellipse(21, pdf.get_y() + 1.8, 1.5, 1.5, "F")
            pdf.set_font("DejaVuSans", "", 10)
            pdf.set_text_color(51, 65, 85)
            pdf.multi_cell(0, 5.5, list_text, border=0, fill=False, markdown=True)
            pdf.set_left_margin(20)
            pdf.ln(2)
            i += 1
            
        # Horizontal Rule
        elif line.strip() == "---":
            pdf.ln(4)
            pdf.set_draw_color(226, 232, 240)
            pdf.set_line_width(0.5)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(4)
            i += 1
            
        # Table
        elif line.startswith("|"):
            headers = [c.strip() for c in line.split("|")[1:-1]]
            i += 1  # Skip headers line
            if i < n and "---" in lines[i]:
                i += 1
            table_rows = []
            while i < n and lines[i].startswith("|"):
                row_cells = [c.strip() for c in lines[i].split("|")[1:-1]]
                table_rows.append(row_cells)
                i += 1
            draw_table(pdf, headers, table_rows)
            
        # Regular paragraph
        else:
            p_lines = []
            while i < n and lines[i].strip() and not any(lines[i].startswith(p) for p in ("#", ">", "-", "|")):
                p_lines.append(lines[i].strip())
                i += 1
            p_text = " ".join(p_lines)
            pdf.set_font("DejaVuSans", "", 10)
            pdf.set_text_color(51, 65, 85)
            pdf.multi_cell(0, 6, p_text, markdown=True)
            pdf.ln(3)
            
    # Output PDF
    out_path = "docs/mejoras_clinicas.pdf"
    # Ensure folder exists
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    pdf.output(out_path)
    print(f"PDF generated successfully at {out_path}")

if __name__ == "__main__":
    main()
