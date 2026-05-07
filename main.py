import streamlit as st
import re
import pandas as pd
import numpy as np
import cv2
from io import BytesIO
from PIL import Image
import pytesseract

# --- 1. ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="โปรแกรมประมวลผลแปลน (กรองสี)", page_icon="💜", layout="centered")

# --- 🛠️ 2. ฟังก์ชันกรองเฉพาะสีฟ้า (Blue Color Filtering) ---
def filter_blue_text(pil_image):
    # แปลงจาก PIL เป็น OpenCV (numpy array)
    img_np = np.array(pil_image.convert('RGB'))
    img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    
    # แปลงเป็นค่าสี HSV เพื่อให้กรองสีได้แม่นยำ
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
    
    # 🎯 กำหนดช่วงสีฟ้า (Blue Range) ของแปลน กฟภ.
    lower_blue = np.array([90, 50, 50])
    upper_blue = np.array([130, 255, 255])
    
    # สร้าง Mask กรองเอาเฉพาะสีในช่วงที่กำหนด
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    
    # กลับสีจาก ตัวหนังสือขาวบนพื้นดำ เป็น ตัวหนังสือดำบนพื้นขาว (เพื่อให้ OCR อ่านง่าย)
    inverted = cv2.bitwise_not(mask)
    
    return Image.fromarray(inverted)

# --- 3. ฟังก์ชันดึงข้อความ ---
def extract_text_from_file(file):
    if file.type == "application/pdf":
        import pdfplumber
        text = ""
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text(layout=True) or ""
        return text
    else:
        img = Image.open(file)
        # 🚀 ขั้นตอนเทพ: กรองเอาเฉพาะสีฟ้าก่อนส่งให้ AI
        filtered_img = filter_blue_text(img)
        # ใช้ psm 11 เพื่อหาข้อความที่เอียงและกระจายตัว
        return pytesseract.image_to_string(filtered_img, lang='eng', config='--psm 11')

def process_pea_codes(full_text, suffix_target):
    summary = {}
    inner_text = re.search(r'\((.*?)\)', suffix_target)
    suffix_for_regex = inner_text.group(1).strip() if inner_text else suffix_target.strip()
    
    # Regex ที่รองรับ จุด (.) และ ขีด (-) ในแถวเดียวกัน
    regex_str = r"([a-zA-Z0-9][a-zA-Z0-9\-\.\s]{1,20})\s*\(\s*" + re.escape(suffix_for_regex) + r"\s*\)"
    
    matches = re.finditer(regex_str, full_text, re.IGNORECASE)
    for match in matches:
        raw_code = match.group(1).strip().upper()
        clean_code = re.sub(r'\s+', '', raw_code)
        
        if re.search(r'[A-Z0-9]', clean_code):
            # ซ่อมรหัสยอดฮิต
            clean_code = re.sub(r'^88-', '8-', clean_code)
            if clean_code == '88': clean_code = '8'
            
            final_code = f"{clean_code}({suffix_for_regex.upper()})"
            summary[final_code] = summary.get(final_code, 0) + 1
    return summary

# --- 4. หน้าจอ UI ---
st.markdown("""<div style="background: linear-gradient(135deg, #0072ff, #00c6ff); color: white; padding: 20px; text-align: center; border-radius: 20px 20px 0 0; margin: 0 -2rem 2rem -2rem;"><h2 style="margin: 0; color: white; font-size: 20px;">🔵 โปรแกรมประมวลผล (กรองเฉพาะรหัสสีฟ้า)</h2></div>""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("เลือกไฟล์แปลน (เน้นไฟล์รูปภาพจะกรองสีได้ดีมาก)", type=["pdf", "png", "jpg", "jpeg"])
suffix = st.text_input("รหัสต่อท้าย:", value="(IN)")

if st.button("🚀 เริ่มกรองสีและประมวลผล"):
    if uploaded_file:
        with st.spinner('กำลังลบเส้นแปลนสีดำและดึงรหัสสีฟ้า...'):
            raw_text = extract_text_from_file(uploaded_file)
            result_dict = process_pea_codes(raw_text, suffix)
            
            if result_dict:
                st.success(f"✅ ตรวจพบรหัสสีฟ้า {len(result_dict)} รายการ")
                df = pd.DataFrame(result_dict.items(), columns=['รหัสอุปกรณ์ (Blue Only)', 'จำนวน'])
                st.table(df)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 โหลด Excel", data=output.getvalue(), file_name="blue_codes.xlsx")
            else:
                st.warning("🔍 ไม่พบรหัสสีฟ้า ลองตรวจสอบความชัดของรูปอีกครั้ง")
    else:
        st.error("❌ กรุณาใส่ไฟล์ก่อนครับ")