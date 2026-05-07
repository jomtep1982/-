import streamlit as st
import re
import pdfplumber
import pandas as pd
from io import BytesIO
from PIL import Image
import pytesseract

# --- 1. การตั้งค่าหน้าจอ ---
st.set_page_config(page_title="โปรแกรมประมาณการ ผบส.", page_icon="💜", layout="centered")

st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #f8f6f9; }
    [data-testid="block-container"] { background-color: white; border-radius: 20px; padding: 1rem 2rem 2rem 2rem; box-shadow: 0 10px 25px rgba(0,0,0,0.05); margin-top: 20px; }
    div.stButton > button:first-child { background-color: #622181; color: white; font-weight: bold; border-radius: 12px; padding: 12px; border: none; }
    </style>
""", unsafe_allow_html=True)

# --- 2. ฟังก์ชันสมอง (Logic) แก้ไขการนับแบบรวมช่องว่าง ---
def extract_text(file):
    text = ""
    if file.type == "application/pdf":
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    else:
        img = Image.open(file)
        # ใช้ psm 3 เพื่อให้อ่านข้อความต่อเนื่องเป็นแถวได้ดีขึ้น
        text = pytesseract.image_to_string(img, lang='tha+eng', config='--psm 3')
    return text

def process_logic(full_text, suffix_target):
    summary = {}
    # ดึงเฉพาะข้อความในวงเล็บออกมา (เช่น IN)
    inner_text = re.search(r'\((.*?)\)', suffix_target)
    inner_text = inner_text.group(1).strip() if inner_text else suffix_target.strip()
    
    # 🔥 ปรับปรุง Regex ใหม่: 
    # ([a-zA-Z0-9\s\.\-]+) -> ให้จับ ตัวอักษร, ตัวเลข, ช่องว่าง (\s), จุด (.), และ ขีด (-) ทั้งหมด
    # ที่อยู่ก่อนหน้าวงเล็บSuffix
    regex_str = r"([a-zA-Z0-9][a-zA-Z0-9\s\.\-]*?)\s*\(\s*" + re.escape(inner_text) + r"\s*\)"
    
    matches = re.finditer(regex_str, full_text, re.IGNORECASE)
    
    for match in matches:
        raw_code = match.group(1).strip().upper()
        
        # ⚡ ขั้นตอนสำคัญ: ลบช่องว่าง "ทั้งหมด" ในรหัสออก เพื่อให้ 12 - R4 . SP กลายเป็น 12-R4.SP
        clean_code = re.sub(r'\s+', '', raw_code)
        
        # ซ่อมรหัสที่ OCR มักอ่านผิด
        clean_code = re.sub(r'^88-', '8-', clean_code)
        if clean_code == '88': clean_code = '8'
        
        if len(clean_code) > 0:
            final_code = f"{clean_code}({inner_text.upper()})"
            summary[final_code] = summary.get(final_code, 0) + 1
            
    return summary

# --- 3. ส่วนหน้าจอ UI ---
st.markdown("""<div style="background: linear-gradient(135deg, #622181, #9d308d); color: white; padding: 20px; text-align: center; border-radius: 20px 20px 0 0; margin: 0 -2rem 2rem -2rem;"><h2 style="margin: 0; color: white; font-size: 20px;">💜 โปรแกรมประมวลผลแปลน ผบส. (V.รวมแถว)</h2></div>""", unsafe_allow_html=True)

input_mode = st.radio("เลือกวิธีนำเข้า:", ["อัปโหลดไฟล์", "ถ่ายรูปจากมือถือ"], horizontal=True)

uploaded_file = None
if input_mode == "อัปโหลดไฟล์":
    uploaded_file = st.file_uploader("เลือกไฟล์ PDF หรือรูปภาพ", type=["pdf", "png", "jpg", "jpeg"])
else:
    uploaded_file = st.camera_input("ส่องไปที่รหัสในแปลนแล้วกดถ่ายรูป")

suffix = st.text_input("ค้นหารหัสที่ลงท้ายด้วย (เช่น (IN)):", value="(IN)")

if st.button("🚀 เริ่มประมวลผลทั้งแถว"):
    if uploaded_file:
        with st.spinner('AI กำลังกวาดอ่านข้อมูลทั้งแถว...'):
            raw_text = extract_text(uploaded_file)
            result_dict = process_logic(raw_text, suffix)
            
            if result_dict:
                st.success(f"✅ ตรวจพบรหัสที่สมบูรณ์ {len(result_dict)} รายการ")
                
                # แสดงผลเป็นตารางแนวตั้งเพื่อให้ดูง่ายในมือถือ
                df = pd.DataFrame(result_dict.items(), columns=['รหัสอุปกรณ์ (รวมแถว)', 'จำนวน'])
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # ปุ่ม Excel
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button("📥 ดาวน์โหลดรายงาน Excel", data=output.getvalue(), file_name="summary.xlsx")
            else:
                st.warning("🔍 ไม่พบรหัสที่ตรงตามเงื่อนไข ลองขยับกล้องให้เห็นทั้งแถวชัดๆ นะครับ")
    else:
        st.error("❌ กรุณาใส่ข้อมูลก่อนครับ")