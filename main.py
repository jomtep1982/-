import streamlit as st
import re
import pandas as pd
import numpy as np
import cv2
from io import BytesIO
from PIL import Image, ImageEnhance
import pytesseract
import fitz  # PyMuPDF

# --- การตั้งค่า Tesseract สำหรับ Cloud ---
# บน Streamlit Cloud ไม่ต้องระบุที่อยู่ .exe เพราะระบบจะเรียกผ่าน 'tesseract' ใน Linux โดยอัตโนมัติ
# (เราจะใช้ไฟล์ packages.txt ในการติดตั้งแทน)

st.set_page_config(page_title="PEA ผบส. Digital Estimator", layout="wide")

# --- 🎨 1. ชุดคำสั่ง CSS ตกแต่งหน้าตา Modern Pro ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Prompt', sans-serif;
        background-color: #0e1117; 
        color: #ffffff;
    }

    .main-header {
        background: linear-gradient(90deg, #622181, #9d308d, #622181);
        background-size: 200% auto;
        padding: 40px;
        border-radius: 25px;
        text-align: center;
        margin-bottom: 40px;
        box-shadow: 0 10px 30px rgba(157, 48, 141, 0.4);
    }
    .main-header h1 {
        font-size: 42px !important;
        font-weight: 600;
        color: white !important;
        margin: 0;
    }

    .input-card {
        background: rgba(255, 255, 255, 0.05);
        padding: 30px;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 25px;
    }

    div.stButton > button:first-child {
        background: linear-gradient(135deg, #9d308d 0%, #622181 100%);
        color: white;
        height: 70px;
        width: 100%;
        border-radius: 15px;
        font-size: 26px !important;
        font-weight: 600;
        border: none;
        transition: all 0.3s ease;
        margin-top: 20px;
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(157, 48, 141, 0.5);
    }

    .modern-table {
        width: 100%;
        border-collapse: collapse;
        margin: 25px 0;
        font-size: 20px;
        border-radius: 15px;
        overflow: hidden;
        background-color: white;
    }
    .modern-table th {
        background-color: #622181;
        color: white;
        padding: 20px;
        text-align: center;
        font-size: 24px;
    }
    .modern-table td {
        padding: 18px;
        text-align: center;
        color: #1f2937;
        border-bottom: 1px solid #e5e7eb;
    }
    .modern-table tr:nth-child(even) { background-color: #f9fafb; }
    .modern-table tr:hover { background-color: #f3e8f9; }

    .stTabs [data-baseweb="tab-list"] { gap: 15px; }
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        background-color: rgba(255,255,255,0.05);
        border-radius: 12px 12px 0 0;
        padding: 10px 30px;
        font-size: 20px !important;
        color: #9ca3af;
    }
    .stTabs [aria-selected="true"] {
        background-color: #9d308d !important;
        color: white !important;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. ฟังก์ชันประมวลผล ---
def process_image(pil_img):
    enhancer = ImageEnhance.Contrast(pil_img)
    pil_img = enhancer.enhance(3.0) 
    img_cv = cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([80, 25, 25]), np.array([150, 255, 255]))
    kernel = np.ones((2,2), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    return Image.fromarray(cv2.bitwise_not(mask))

def extract_codes(page_img, target_suffix):
    s_clean = target_suffix.replace('(', '').replace(')', '').strip().upper()
    
    # อ่านข้อความ (lang='eng+tha' ต้องมี tesseract-ocr-tha ใน packages.txt)
    raw_text = pytesseract.image_to_string(page_img, lang='eng+tha', config='--psm 11')
    
    raw_text = raw_text.replace('@', '8').replace('&', '8')
    found = []
    
    for line in raw_text.split('\n'):
        pattern = r"([A-Za-z0-9\-\.\s]+)\(" + re.escape(s_clean) + r"\)"
        for m in re.finditer(pattern, line, re.IGNORECASE):
            code_raw = m.group(1)
            code = re.sub(r'\s+', '', code_raw)
            code = re.sub(r'[^a-zA-Z0-9\-\.]', '', code)
            code = re.sub(r'\d{7,}', '', code)
            code = re.sub(r'^88-', '8-', code.upper())
            code = code.strip('-').strip('.')
            if len(code) >= 1: 
                found.append(f"{code}({s_clean})")
    return found

# --- 3. ส่วนหน้าจอโปรแกรม ---
st.markdown('<div class="main-header"><h1>โปรแกรมประมาณการระบบจำหน่าย ผบส. กฟจ.ศก</h1></div>', unsafe_allow_html=True)

st.markdown('<div class="input-card">', unsafe_allow_html=True)
col_cfg1, col_cfg2 = st.columns(2)
with col_cfg1:
    suffix_val = st.text_input("🔍 ข้อความต่อท้ายที่ค้นหา", value="(IN)")
with col_cfg2:
    mode_val = st.selectbox("🎨 โหมดการอ่านสี", ["สีฟ้าเท่านั้น", "อ่านทุกสี (ALL)"])
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<h3>📂 เลือกไฟล์แปลนระบบ (แผ่นที่ 1, 2, 3...)</h3>', unsafe_allow_html=True)
if 'file_count' not in st.session_state: st.session_state.file_count = 1
uploaded_dict = {}

for i in range(st.session_state.file_count):
    st.markdown(f"**แผ่นที่ {i+1}**")
    uploaded_dict[i] = st.file_uploader(f"แผ่นที่_{i+1}", type=["pdf", "png", "jpg"], label_visibility="collapsed")

if st.button("+ เพิ่มช่องอัปโหลดแผ่นถัดไป"):
    st.session_state.file_count += 1
    st.rerun()

if st.button("🚀 เริ่มคำนวณและสรุปผลทุกแผ่น"):
    all_final_data = [] 
    with st.spinner('ผบส. Digital AI กำลังวิเคราะห์แปลน...'):
        for i in range(st.session_state.file_count):
            f = uploaded_dict.get(i)
            if f:
                if f.type == "application/pdf":
                    doc = fitz.open(stream=f.read(), filetype="pdf")
                    imgs = []
                    for p in doc:
                        pix = p.get_pixmap(dpi=300)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        imgs.append(img)
                else:
                    imgs = [Image.open(f)]
                
                codes_in_file = []
                for img in imgs:
                    processed_img = process_image(img) if mode_val == "สีฟ้าเท่านั้น" else img
                    codes_in_file.extend(extract_codes(processed_img, suffix_val))
                
                if codes_in_file:
                    df = pd.DataFrame(codes_in_file, columns=['รหัสอุปกรณ์']).value_counts().reset_index()
                    df.columns = ['รหัสอุปกรณ์', 'จำนวน']
                    all_final_data.append((f"แผ่นที่ {i+1}", df))

    if all_final_data:
        st.markdown("<br><h2 style='text-align:center; color:#9d308d;'>📊 ผลการประมาณการแยกตามแผ่น</h2>", unsafe_allow_html=True)
        tab_names = [name for name, _ in all_final_data]
        tabs = st.tabs(tab_names)
        
        for idx, (name, df) in enumerate(all_final_data):
            with tabs[idx]:
                html = '<table class="modern-table"><thead><tr><th>รหัสอุปกรณ์</th><th>จำนวน (ชุด)</th></tr></thead><tbody>'
                for _, row in df.iterrows():
                    html += f'<tr><td>{row["รหัสอุปกรณ์"]}</td><td>{row["จำนวน"]}</td></tr>'
                html += '</tbody></table>'
                st.markdown(html, unsafe_allow_html=True)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for name, df in all_final_data:
                df.to_excel(writer, sheet_name=name, index=False)
        st.download_button("📥 ดาวน์โหลดรายงานสรุป ผบส. (Excel)", data=output.getvalue(), file_name="ผบส_Summary_Pro.xlsx", use_container_width=True)