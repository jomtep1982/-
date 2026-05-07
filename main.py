import streamlit as st
import re
import pdfplumber
import pandas as pd
from io import BytesIO
from PIL import Image
import pytesseract

# --- 1. ตั้งค่าหน้าเว็บและ CSS (เหมือนเดิม) ---
st.set_page_config(page_title="โปรแกรมประมาณการ ผบส.", page_icon="💜", layout="centered")

# --- 2. ฟังก์ชันสมอง (Logic) สำหรับอ่านข้อความ ---
def extract_text(file):
    text = ""
    if file.type == "application/pdf":
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    else:
        # ถ้าเป็นรูปภาพ (JPG/PNG) หรือภาพจากกล้อง
        img = Image.open(file)
        # สั่งให้ AI อ่านภาษาไทยและอังกฤษ
        text = pytesseract.image_to_string(img, lang='tha+eng')
    return text

def process_logic(full_text, suffix_target):
    summary = {}
    inner_text = re.search(r'\((.*?)\)', suffix_target)
    inner_text = inner_text.group(1).strip() if inner_text else suffix_target.strip()
    
    regex_str = r"([a-zA-Z0-9][a-zA-Z0-9\s\-\.]*?)\s*\(\s*" + re.escape(inner_text) + r"\s*\)"
    matches = re.finditer(regex_str, full_text, re.IGNORECASE)
    
    for match in matches:
        raw_code = match.group(1)
        clean_code = re.sub(r'\s+', '', raw_code)
        # ชุดซ่อมแซมรหัส
        clean_code = re.sub(r'^88-', '8-', clean_code)
        if clean_code == '88': clean_code = '8'
        if len(clean_code) > 0:
            final_code = f"{clean_code}({inner_text.upper()})"
            summary[final_code] = summary.get(final_code, 0) + 1
    return summary

# --- 3. ส่วนหน้าจอ UI ---
st.markdown("""<div style="background: linear-gradient(135deg, #622181, #9d308d); color: white; padding: 25px; text-align: center; border-radius: 20px 20px 0 0; margin: 0 -2rem 2rem -2rem;"><h2 style="margin: 0; color: white; font-size: 22px;">💜 โปรแกรมประมาณการ (ฉบับออกหน้างาน)</h2></div>""", unsafe_allow_html=True)

st.write("")
input_mode = st.radio("เลือกวิธีนำเข้าข้อมูล:", ["อัปโหลดไฟล์ (PDF/รูปภาพ)", "ถ่ายรูปจากกล้องมือถือ"], horizontal=True)

uploaded_file = None
if input_mode == "อัปโหลดไฟล์ (PDF/รูปภาพ)":
    uploaded_file = st.file_uploader("เลือกไฟล์แปลน...", type=["pdf", "png", "jpg", "jpeg"])
else:
    uploaded_file = st.camera_input("ส่องไปที่รหัสในแปลนแล้วกดถ่ายรูป")

suffix = st.text_input("ข้อความต่อท้ายที่ต้องการค้นหา", value="(IN)")

if st.button("เริ่มคำนวณและประมาณการ", use_container_width=True):
    if uploaded_file:
        with st.spinner('AI กำลังเพ่งอ่านรหัส... กรุณารอสักครู่ ⏳'):
            raw_text = extract_text(uploaded_file)
            result_dict = process_logic(raw_text, suffix)
            
            if result_dict:
                st.success("✅ อ่านรหัสสำเร็จ!")
                df = pd.DataFrame([result_dict])
                st.table(df)
                
                # ปุ่มดาวน์โหลด Excel
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 ดาวน์โหลดรายงาน Excel", data=output.getvalue(), file_name="report.xlsx")
            else:
                st.warning("🔍 ไม่พบรหัสที่ตรงตามเงื่อนไข ลองถ่ายรูปให้ชัดขึ้นนะครับ")
    else:
        st.error("❌ กรุณาเลือกไฟล์หรือถ่ายรูปก่อนครับ")