import streamlit as st
import re
import pandas as pd
import numpy as np
import cv2
from io import BytesIO
from PIL import Image, ImageEnhance
import pytesseract
from pdf2image import convert_from_bytes

st.set_page_config(page_title="โปรแกรมประมวลผลแปลน PEA", page_icon="💜", layout="centered")

# --- 1. ฟังก์ชันกรองสีฟ้า (ทำงานได้เพอร์เฟกต์แล้ว!) ---
def process_blue_filter_advanced(pil_img):
    enhancer = ImageEnhance.Contrast(pil_img)
    pil_img = enhancer.enhance(2.0)
    
    img_cv = cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
    
    lower_blue = np.array([85, 30, 30]) 
    upper_blue = np.array([145, 255, 255])
    
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    
    kernel = np.ones((2,2), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    
    return Image.fromarray(cv2.bitwise_not(mask))

# --- 2. ฟังก์ชันซ่อมและทำความสะอาดรหัส ---
def clean_pea_code(text):
    code = re.sub(r'[^A-Z0-9\-\.]', '', text) # อนุญาตแค่อักษร เลข ขีด จุด
    code = re.sub(r'\d{6,}', '', code) # ตัดเลขพิกัดเสายาวๆ ทิ้ง
    return code.strip('-').strip('.')

# --- 3. หน้าจอ UI ---
st.markdown("""<div style="background: linear-gradient(135deg, #622181, #9d308d); color: white; padding: 25px; text-align: center; border-radius: 20px 20px 0 0; margin: 0 -2rem 2rem -2rem;"><h2 style="margin: 0; color: white; font-size: 22px;">💜 โปรแกรมประมวลผลแปลน (V.บีบอัดข้อความ)</h2></div>""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("อัปโหลดแปลน PDF หรือรูปภาพ", type=["pdf", "png", "jpg", "jpeg"])
suffix = st.text_input("รหัสต่อท้ายที่ต้องการนับ (เช่น (IN)):", value="(IN)")
show_debug = st.checkbox("🔍 ตรวจสอบภาพที่ AI มองเห็น")

if st.button("🚀 เริ่มประมวลผลแบบละเอียด"):
    if uploaded_file:
        with st.spinner('กำลังใช้ AI สกัดรหัสและเชื่อมต่อข้อความเข้าด้วยกัน...'):
            if uploaded_file.type == "application/pdf":
                pages = convert_from_bytes(uploaded_file.read(), dpi=300)
            else:
                pages = [Image.open(uploaded_file)]
            
            all_results = {}
            for i, page in enumerate(pages):
                processed_img = process_blue_filter_advanced(page)
                
                if show_debug:
                    st.image(processed_img, caption=f"หน้า {i+1}: ภาพชัดเจน! AI กำลังอ่านและบีบอัดข้อความ")
                
                # 1. ให้ AI อ่านข้อความทั้งหมดออกมาก่อน
                raw_text = pytesseract.image_to_string(processed_img, lang='eng', config='--psm 11')
                
                # 🚀 2. ไม้ตาย: ลบช่องว่างและขึ้นบรรทัดใหม่ "ทั้งหมด" ออกไป!
                # (1 2 - R 4 ( I N ) จะถูกเชื่อมกลายเป็น 12-R4(IN) ทันที)
                compact_text = re.sub(r'\s+', '', raw_text).upper()
                
                # แก้ไขกรณี AI มองวงเล็บเอียงๆ เป็นปีกกา
                compact_text = re.sub(r'[\[\{]', '(', compact_text)
                compact_text = re.sub(r'[\]\}]', ')', compact_text)
                
                # 3. เตรียมคำที่ต้องการค้นหา
                s_clean = suffix.replace('(', '').replace(')', '').strip().upper()
                
                # 4. ค้นหาข้อมูล (หาตัวอักษร 2-25 ตัวที่อยู่ติดกับ (IN))
                regex_str = r"([A-Z0-9\-\.]{2,25})\(" + re.escape(s_clean) + r"\)"
                matches = re.finditer(regex_str, compact_text)
                
                for m in matches:
                    code = clean_pea_code(m.group(1))
                    code = re.sub(r'^88-', '8-', code) # ซ่อม 88- เป็น 8-
                    
                    if len(code) >= 2 and re.search(r'[A-Z0-9]', code):
                        final = f"{code}({s_clean})"
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
                st.error("🔍 ยังไม่พบรหัส! ลองตรวจสอบความคมชัดอีกครั้งครับ")
    else:
        st.error("❌ กรุณาเลือกไฟล์ก่อนครับ")
