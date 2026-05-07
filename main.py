import streamlit as st
import re
import pdfplumber
import pandas as pd
from io import BytesIO

# --- 1. ตั้งค่าหน้าเว็บและ CSS (เหมือนเดิม) ---
st.set_page_config(page_title="โปรแกรมประมาณการ ผบส.", page_icon="💜", layout="centered")

st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #f8f6f9; }
    [data-testid="block-container"] { background-color: white; border-radius: 20px; padding: 0rem 2rem 2rem 2rem; box-shadow: 0 20px 40px rgba(0,0,0,0.1); margin-top: 30px; }
    div.stButton > button:first-child { background-color: #622181; color: white; font-weight: bold; border-radius: 10px; padding: 15px; border: none; }
    div.stButton > button:first-child:hover { background-color: #9d308d; box-shadow: 0 5px 15px rgba(98, 33, 129, 0.3); }
    </style>
""", unsafe_allow_html=True)

st.markdown("""<div style="background: linear-gradient(135deg, #622181, #9d308d); color: white; padding: 25px; text-align: center; border-radius: 20px 20px 0 0; margin: 0 -2rem 2rem -2rem;"><h2 style="margin: 0; color: white; font-size: 22px;">💜 โปรแกรมประมาณการระบบจำหน่าย ผบส. กฟจ.ศก</h2></div>""", unsafe_allow_html=True)

# --- 2. ฟังก์ชันสมอง (Logic) สำหรับสกัดรหัสและซ่อมคำผิด ---
def process_ocr_logic(file, suffix_target):
    summary = {}
    full_text = ""
    
    # อ่าน PDF
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text() or ""

    # เตรียม Suffix (เช่น IN)
    inner_text = re.search(r'\((.*?)\)', suffix_target)
    inner_text = inner_text.group(1).strip() if inner_text else suffix_target.strip()
    
    # Regex ดักจับรหัส + วงเล็บ
    regex_str = r"([a-zA-Z0-9][a-zA-Z0-9\s\-\.]*?)\s*\(\s*" + re.escape(inner_text) + r"\s*\)"
    matches = re.finditer(regex_str, full_text, re.IGNORECASE)
    
    for match in matches:
        raw_code = match.group(1)
        clean_code = re.sub(r'\s+', '', raw_code)
        
        # --- 🚨 ชุดซ่อมแซมรหัส (เหมือน Apps Script เป๊ะ) ---
        clean_code = re.sub(r'^88-', '8-', clean_code)
        if clean_code == '88': clean_code = '8'
        clean_code = re.sub(r'--+', '-', clean_code)
        clean_code = clean_code.replace('DDE', 'DE')
        
        if len(clean_code) > 0:
            final_code = f"{clean_code}({inner_text.upper()})"
            summary[final_code] = summary.get(final_code, 0) + 1
            
    return summary

# --- 3. ส่วนหน้าจอรับข้อมูล ---
st.markdown("#### 📌 เงื่อนไขการค้นหา")
col1, col2 = st.columns(2)
with col1:
    suffix = st.text_input("ข้อความต่อท้าย", value="(IN)")
with col2:
    color = st.text_input("สีตัวอักษร", value="ALL")

st.markdown("#### 📁 เลือกไฟล์แปลนระบบ")
uploaded_file = st.file_uploader("อัปโหลดไฟล์แปลน (PDF)", type=["pdf"])

if st.button("เริ่มคำนวณและประมาณการ", use_container_width=True):
    if uploaded_file:
        with st.spinner('กำลังประมวลผล...'):
            # รันการคำนวณจริง
            result_dict = process_ocr_logic(uploaded_file, suffix)
            
            if result_dict:
                st.success("✅ ประมวลผลสำเร็จ!")
                
                # แสดงตารางผลลัพธ์
                df = pd.DataFrame([result_dict])
                st.markdown("##### 📍 ผลการประมวลผล:")
                st.table(df) # แสดงตารางสวยงามเหมือนในรูป

                # --- 4. การส่งออก Excel ---
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Summary')
                
                st.download_button(
                    label="📥 ดาวน์โหลดรายงาน Excel",
                    data=output.getvalue(),
                    file_name=f"รายงานประมาณการ_{uploaded_file.name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("🔍 ไม่พบรหัสอุปกรณ์ที่ตรงตามเงื่อนไขในไฟล์นี้")
    else:
        st.error("❌ กรุณาอัปโหลดไฟล์ก่อนครับ")