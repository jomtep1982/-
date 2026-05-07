import streamlit as st
import re
import pandas as pd
import numpy as np
import cv2
from io import BytesIO
from PIL import Image, ImageOps, ImageEnhance
import pytesseract
from pdf2image import convert_from_bytes

st.set_page_config(page_title="โปรแกรมประมวลผลแปลน PEA", page_icon="💜", layout="centered")

# --- 🛠️ 1. ฟังก์ชันกรองสีฟ้า (ปรับปรุงเพื่อเส้นบาง) ---
def process_blue_filter_advanced(pil_img):
    # เปลี่ยนเป็น RGB และเพิ่มความคมชัดก่อน
    enhancer = ImageEnhance.Contrast(pil_img)
    pil_img = enhancer.enhance(2.0)
    
    img_cv = cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
    
    # 🎯 ช่วงสีฟ้าแบบกว้างพิเศษ (จับสีฟ้าจางและฟ้าเข้มได้ครบ)
    lower_blue = np.array([85, 30, 30]) 
    upper_blue = np.array([145, 255, 255])
    
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    
    # 🚀 หัวใจสำคัญ: ทำให้เส้นตัวหนังสือหนาขึ้น (Dilation)
    kernel = np.ones((2,2), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    
    # กลับสีพื้นขาว ตัวดำ
    return Image.fromarray(cv2.bitwise_not(mask))

# --- 2. ฟังก์ชันซ่อมรหัส ---
def clean_pea_code(text):
    # ลบช่องว่างและอักขระแปลกปลอม
    code = re.sub(r'[^a-zA-Z0-9\-\.\(\)]', '', text)
    # ตัดเลขพิกัดเสาที่ยาวเกินไป (ถ้ามีเลขติดกัน 7 ตัวขึ้นไป)
    code = re.sub(r'\d{7,}', '', code)
    return code.strip('-').strip('.')

# --- 3. หน้าจอ UI ---
st.markdown("""<div style="background: linear-gradient(135deg, #622181, #9d308d); color: white; padding: 25px; text-align: center; border-radius: 20px 20px 0 0; margin: 0 -2rem 2rem -2rem;"><h2 style="margin: 0; color: white; font-size: 22px;">💜 โปรแกรมประมวลผลแปลน (V.อ่านเส้นบางสีฟ้า)</h2></div>""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("อัปโหลดแปลน PDF หรือรูปภาพ", type=["pdf", "png", "jpg", "jpeg"])
suffix = st.text_input("รหัสต่อท้ายที่ต้องการนับ (เช่น (IN)):", value="(IN)")
show_debug = st.checkbox("🔍 ตรวจสอบภาพที่ AI มองเห็น (ต้องเห็นตัวหนังสือชัดเจน)")

if st.button("🚀 เริ่มประมวลผลแบบละเอียด"):
    if uploaded_file:
        with st.spinner('กำลังใช้ AI สกัดรหัสจากแปลน...'):
            if uploaded_file.type == "application/pdf":
                # 🚀 ใช้ DPI 300 เพื่อความคมชัดสูงสุด
                pages = convert_from_bytes(uploaded_file.read(), dpi=300)
            else:
                pages = [Image.open(uploaded_file)]
            
            all_results = {}
            for i, page in enumerate(pages):
                processed_img = process_blue_filter_advanced(page)
                
                if show_debug:
                    st.image(processed_img, caption=f"หน้า {i+1}: ถ้าเห็นตัวหนังสือดำชัดเจนแบบนี้ AI จะนับได้แม่นยำครับ")
                
                # อ่าน OCR (โหมด psm 11 สำหรับข้อความกระจายตัว)
                raw_text = pytesseract.image_to_string(processed_img, lang='eng', config='--psm 11')
                
                # Regex ค้นหา (รองรับทั้งขีดและจุด)
                s_clean = suffix.replace('(', '').replace(')', '').strip()
                regex_str = r"([a-zA-Z0-9\-\.]{1,20})\s*\(\s*" + re.escape(s_clean) + r"\s*\)"
                
                matches = re.finditer(regex_str, raw_text, re.IGNORECASE)
                for m in matches:
                    code = clean_pea_code(m.group(1))
                    if len(code) >= 2: # ป้องกันตัวอักษรขยะตัวเดียว
                        final = f"{code.upper()}({s_clean.upper()})"
                        all_results[final] = all_results.get(final, 0) + 1

            if all_results:
                st.success(f"✅ ตรวจพบรหัสสีฟ้า {sum(all_results.values())} ชุด")
                df = pd.DataFrame(all_results.items(), columns=['รหัสอุปกรณ์', 'จำนวน'])
                st.table(df)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 โหลด Excel", data=output.getvalue(), file_name="pea_summary.xlsx")
            else:
                st.error("🔍 ยังไม่พบรหัส! ลองดูรูปที่ AI มองเห็นว่าตัวหนังสือขาดหายไปหรือไม่")
    else:
        st.error("❌ กรุณาเลือกไฟล์ก่อนครับ")