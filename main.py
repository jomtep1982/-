import streamlit as st
import re
import pandas as pd
from io import BytesIO
from PIL import Image
import pytesseract

# --- 1. การตั้งค่าหน้าจอ ---
st.set_page_config(page_title="โปรแกรมประมวลผลแปลน กฟภ.", page_icon="💜", layout="centered")

st.markdown("""<style>[data-testid="stAppViewContainer"] { background-color: #f8f6f9; }[data-testid="block-container"] { background-color: white; border-radius: 20px; padding: 1rem 2rem 2rem 2rem; box-shadow: 0 10px 25px rgba(0,0,0,0.05); margin-top: 20px; }div.stButton > button:first-child { background-color: #622181; color: white; font-weight: bold; border-radius: 12px; padding: 12px; border: none; }</style>""", unsafe_allow_html=True)

# --- 2. ฟังก์ชันสมอง (Logic) ปรับปรุงใหม่เพื่อลดขยะ ---
def extract_text_from_file(file):
    if file.type == "application/pdf":
        # เปลี่ยนมาใช้การอ่านแบบคำ (Word-based) เพื่อลดการดึงพิกัดมั่ว
        import pdfplumber
        text = ""
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                # ดึงข้อความโดยพยายามรักษาตำแหน่งเดิม (layout=True)
                page_text = page.extract_text(layout=True)
                if page_text: text += page_text
        return text
    else:
        # สำหรับรูปภาพ/ถ่ายรูป ใช้ config พิเศษเพื่อให้อ่านตัวหนังสือเล็กๆ ได้ดีขึ้น
        img = Image.open(file).convert('RGB')
        return pytesseract.image_to_string(img, lang='tha+eng', config='--psm 11 --oem 3')

def process_pea_codes(full_text, suffix_target):
    summary = {}
    inner_text = re.search(r'\((.*?)\)', suffix_target)
    suffix_for_regex = inner_text.group(1).strip() if inner_text else suffix_target.strip()
    
    # 🔥 REGEX รุ่นปรับปรุง: 
    # 1. จำกัดให้เริ่มด้วยตัวอักษรหรือตัวเลขเท่านั้น
    # 2. จำกัดความยาวไม่เกิน 15 ตัวอักษร (ตัดรหัสพิกัดยาวๆ ทิ้ง)
    # 3. ไม่เอาขีด (-) ที่อยู่หน้าสุดของคำ
    regex_str = r"(?:^|[\s])([a-zA-Z0-9][a-zA-Z0-9\-\.]{1,15})\s*\(\s*" + re.escape(suffix_for_regex) + r"\s*\)"
    
    matches = re.finditer(regex_str, full_text, re.IGNORECASE)
    
    for match in matches:
        raw_code = match.group(1).strip().upper()
        clean_code = re.sub(r'\s+', '', raw_code)
        
        # กรองขยะเบื้องต้น: รหัสต้องมีอักษรภาษาอังกฤษหรือตัวเลข และไม่เป็นแค่จุดหรือขีด
        if re.search(r'[A-Z0-9]', clean_code):
            # ซ่อมรหัสยอดฮิต
            clean_code = re.sub(r'^88-', '8-', clean_code)
            if clean_code == '88': clean_code = '8'
            
            # ป้องกันรหัสซ้ำซ้อนที่อ่านติดกัน
            final_code = f"{clean_code}({suffix_for_regex.upper()})"
            summary[final_code] = summary.get(final_code, 0) + 1
            
    return summary

# --- 3. ส่วนหน้าจอ UI ---
st.markdown("""<div style="background: linear-gradient(135deg, #622181, #9d308d); color: white; padding: 20px; text-align: center; border-radius: 20px 20px 0 0; margin: 0 -2rem 2rem -2rem;"><h2 style="margin: 0; color: white; font-size: 20px;">💜 โปรแกรมประมวลผลแปลน (V.ลดสัญญาณรบกวน)</h2></div>""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("เลือกไฟล์แปลน (PDF/JPG/PNG)...", type=["pdf", "png", "jpg", "jpeg"])
suffix = st.text_input("ค้นหารหัสที่ลงท้ายด้วย:", value="(IN)")

if st.button("🚀 เริ่มคำนวณและประมาณการ"):
    if uploaded_file:
        with st.spinner('กำลังกรองรหัสขยะและนับจำนวน...'):
            raw_text = extract_text_from_file(uploaded_file)
            result_dict = process_pea_codes(raw_text, suffix)
            
            if result_dict:
                st.success(f"✅ ตรวจพบรหัสที่ถูกต้อง {len(result_dict)} รายการ")
                
                # แสดงผลเป็นตาราง
                df = pd.DataFrame(result_dict.items(), columns=['รหัสอุปกรณ์', 'จำนวน'])
                st.table(df)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 ดาวน์โหลดรายงาน Excel", data=output.getvalue(), file_name="summary.xlsx")
            else:
                st.warning("🔍 ไม่พบรหัสที่ตรงตามเงื่อนไข ลองตรวจสอบว่าไฟล์ชัดเจนหรือไม่")
    else:
        st.error("❌ กรุณาใส่ไฟล์ก่อนครับ")