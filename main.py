import streamlit as st
import re
import pandas as pd
import numpy as np
import cv2
from io import BytesIO
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes

st.set_page_config(page_title="โปรแกรมประมวลผลแปลน PEA", page_icon="💜", layout="centered")

# --- 🛠️ 1. ฟังก์ชันกรองสี (ปรับให้มองเห็นกว้างขึ้น) ---
def process_blue_filter(pil_img):
    img_cv = cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
    
    # 🎯 ขยายช่วงสีฟ้าให้กว้างขึ้น (Hue 75-160) เพื่อดักจับทุกเฉด
    lower_blue = np.array([75, 20, 20]) 
    upper_blue = np.array([160, 255, 255])
    
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    
    # ลบจุดรบกวนเล็กๆ
    kernel = np.ones((1,1), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    
    # กลับสี (พื้นขาว ตัวดำ) เพื่อให้ OCR อ่านง่าย
    return Image.fromarray(cv2.bitwise_not(mask))

# --- 2. ฟังก์ชันทำความสะอาดรหัส ---
def clean_pea_code(text):
    code = re.sub(r'\s+', '', text)
    # ตัดเลขพิกัดยาวๆ (6 ตัวขึ้นไป) ออกจากหน้าชื่อรหัส
    code = re.sub(r'^\d{6,}', '', code)
    # ตัดขยะหน้า/หลัง
    code = code.strip('-').strip('.')
    return code

# --- 3. หน้าจอหลัก ---
st.markdown("""<div style="background: linear-gradient(135deg, #622181, #9d308d); color: white; padding: 25px; text-align: center; border-radius: 20px 20px 0 0; margin: 0 -2rem 2rem -2rem;"><h2 style="margin: 0; color: white; font-size: 22px;">💜 โปรแกรมประมวลผลแปลน (V.ตาสว่าง)</h2></div>""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("อัปโหลดแปลน PDF หรือรูปภาพ", type=["pdf", "png", "jpg", "jpeg"])
suffix = st.text_input("ค้นหารหัสที่ลงท้ายด้วย:", value="(IN)")

# 💡 เพิ่มโหมดช่วยตรวจสอบ (Debug)
show_debug = st.checkbox("🔍 แสดงภาพที่ AI มองเห็น (เพื่อตรวจเช็กสี)")

if st.button("🚀 เริ่มประมวลผล"):
    if uploaded_file:
        with st.spinner('กำลังประมวลผล...'):
            # 1. แปลงไฟล์
            if uploaded_file.type == "application/pdf":
                pages = convert_from_bytes(uploaded_file.read(), dpi=200)
            else:
                pages = [Image.open(uploaded_file)]
            
            all_results = {}
            
            for i, page in enumerate(pages):
                # 2. กรองสี
                processed_img = process_blue_filter(page)
                
                if show_debug:
                    st.image(processed_img, caption=f"ภาพหน้า {i+1} ที่กรองสีฟ้าแล้ว (ต้องเห็นรหัสเป็นสีดำชัดเจน)", use_container_width=True)
                
                # 3. อ่าน OCR (ใช้ psm 11 สำหรับข้อความกระจายตัว)
                raw_text = pytesseract.image_to_string(processed_img, lang='eng', config='--psm 11')
                
                # 4. ค้นหารหัส
                inner_text = re.search(r'\((.*?)\)', suffix)
                s_target = inner_text.group(1).strip() if inner_text else suffix.strip()
                
                regex_str = r"([a-zA-Z0-9\-\.]{1,20})\s*\(\s*" + re.escape(s_target) + r"\s*\)"
                matches = re.finditer(regex_str, raw_text, re.IGNORECASE)
                
                for m in matches:
                    c = clean_pea_code(m.group(1))
                    if re.search(r'[A-Z0-9]', c):
                        final = f"{c.upper()}({s_target.upper()})"
                        all_results[final] = all_results.get(final, 0) + 1

            if all_results:
                st.success(f"✅ ตรวจพบรหัส {len(all_results)} รายการ")
                df = pd.DataFrame(all_results.items(), columns=['รหัสอุปกรณ์', 'จำนวน'])
                st.table(df)
            else:
                st.warning("🔍 ยังไม่พบรหัส! แนะนำให้ติ๊กถูกที่ 'แสดงภาพที่ AI มองเห็น' เพื่อดูว่ารหัสหายไปหรือไม่")
    else:
        st.error("❌ กรุณาเลือกไฟล์ก่อนครับ")