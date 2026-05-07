import streamlit as st
import re
import pandas as pd
import numpy as np
import cv2
from io import BytesIO
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes

# --- 1. ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="โปรแกรมประมวลผลแปลน PEA", page_icon="💜", layout="centered")

# --- 🛠️ 2. ฟังก์ชันกรองสีฟ้า และขจัดขยะ (Noise) ---
def process_image_blue_only(pil_img):
    # แปลงภาพเพื่อใช้ OpenCV
    img_cv = cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
    
    # 🎯 ช่วงสีฟ้าของแปลน (ปรับให้กว้างขึ้นครอบคลุมสีฟ้าเข้ม/อ่อน)
    lower_blue = np.array([90, 40, 40])
    upper_blue = np.array([140, 255, 255])
    
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    
    # ขจัดจุดรบกวนเล็กๆ (Denoising)
    kernel = np.ones((2,2), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    # กลับสีให้พื้นขาว ตัวหนังสือดำ (OCR ชอบแบบนี้)
    return Image.fromarray(cv2.bitwise_not(mask))

# --- 3. ฟังก์ชันดึงข้อความและซ่อมรหัส ---
def clean_pea_code(text):
    # ลบช่องว่าง
    code = re.sub(r'\s+', '', text)
    # 🚨 กฎเหล็ก: ถ้ามีตัวเลขติดกันเกิน 6 ตัวที่หน้าสุด (พวกเลขพิกัด/เลขเสา) ให้ตัดทิ้ง
    code = re.sub(r'^\d{6,}', '', code)
    # ตัดขีดที่หลงมาหน้าสุด
    code = code.lstrip('-').lstrip('.')
    # ซ่อมรหัสยอดฮิต
    code = re.sub(r'^88-', '8-', code)
    return code

def extract_from_any_file(file, suffix_target):
    images = []
    if file.type == "application/pdf":
        # แปลง PDF เป็นรูปภาพ (300 DPI เพื่อความชัด)
        images = convert_from_bytes(file.read(), dpi=300)
    else:
        images = [Image.open(file)]
    
    all_summary = {}
    inner_text = re.search(r'\((.*?)\)', suffix_target)
    suffix_for_regex = inner_text.group(1).strip() if inner_text else suffix_target.strip()

    for img in images:
        # 1. กรองสีฟ้า
        processed = process_image_blue_only(img)
        # 2. อ่าน OCR
        raw_text = pytesseract.image_to_string(processed, lang='eng', config='--psm 11')
        
        # 3. ค้นหาด้วย Regex (จำกัดความยาวเพื่อไม่ให้กวาดขยะมาเยอะ)
        regex_str = r"([a-zA-Z0-9\-\.]{1,20})\s*\(\s*" + re.escape(suffix_for_regex) + r"\s*\)"
        matches = re.finditer(regex_str, raw_text, re.IGNORECASE)
        
        for match in matches:
            code = clean_pea_code(match.group(1))
            if re.search(r'[A-Z0-9]', code): # ต้องมีตัวอักษรหรือตัวเลข
                final = f"{code.upper()}({suffix_for_regex.upper()})"
                all_summary[final] = all_summary.get(final, 0) + 1
                
    return all_summary

# --- 4. ส่วนหน้าจอ UI ---
st.markdown("""<div style="background: linear-gradient(135deg, #622181, #9d308d); color: white; padding: 25px; text-align: center; border-radius: 20px 20px 0 0; margin: 0 -2rem 2rem -2rem;"><h2 style="margin: 0; color: white; font-size: 22px;">💜 โปรแกรมประมวลผลแปลน PEA (V.สมบูรณ์แบบ)</h2></div>""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("อัปโหลดแปลน PDF หรือรูปภาพ (จะกรองสีให้อัตโนมัติ)", type=["pdf", "png", "jpg", "jpeg"])
suffix = st.text_input("ค้นหารหัสที่ลงท้ายด้วย:", value="(IN)")

if st.button("🚀 เริ่มประมวลผลแบบละเอียด"):
    if uploaded_file:
        with st.spinner('กำลังแปลงไฟล์และกรองเฉพาะรหัสสีฟ้า...'):
            results = extract_from_any_file(uploaded_file, suffix)
            
            if results:
                st.success(f"✅ ตรวจพบรหัสสีฟ้าที่ถูกต้อง {len(results)} รายการ")
                df = pd.DataFrame(results.items(), columns=['รหัสอุปกรณ์', 'จำนวน'])
                st.table(df)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 ดาวน์โหลดรายงาน Excel", data=output.getvalue(), file_name="summary_pea.xlsx")
            else:
                st.warning("🔍 ไม่พบรหัสสีฟ้า ลองตรวจสอบว่าไฟล์ต้นฉบับชัดเจนหรือไม่")