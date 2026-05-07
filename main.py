import streamlit as st
import re
import pandas as pd
from io import BytesIO
from PIL import Image
import pytesseract

# --- 1. การตั้งค่าหน้าจอและ CSS ---
st.set_page_config(page_title="โปรแกรมประมวลผลแปลน กฟภ.", page_icon="💜", layout="centered")

st.markdown("""<style>[data-testid="stAppViewContainer"] { background-color: #f8f6f9; }[data-testid="block-container"] { background-color: white; border-radius: 20px; padding: 1rem 2rem 2rem 2rem; box-shadow: 0 10px 25px rgba(0,0,0,0.05); margin-top: 20px; }div.stButton > button:first-child { background-color: #622181; color: white; font-weight: bold; border-radius: 12px; padding: 12px; border: none; }</style>""", unsafe_allow_html=True)

# --- 🛠️ 2. ฟังก์ชันแก้ไขภาพเอียง (Deskewing) ---
def image_deskewing(pil_image):
    # เปลี่ยนภาพเป็น RGB เพื่อให้ OSD ตรวจสอบได้
    rgb_img = pil_image.convert('RGB')
    try:
        # ใช้วิธีพิเศษ OSD ตรวจสอบทิศทางว่าภาพเอียงกี่องศา
        osd = pytesseract.image_to_osd(rgb_img)
        # สแกนหาคำว่า Rotate: ว่าเป็นเลขอะไร
        rotation_match = re.search(r'(?<=Rotate: )\d+', osd)
        if rotation_match:
            angle_to_rotate = int(rotation_match.group(0))
            if angle_to_rotate != 0:
                # 🚀 เสกภาพเอียงให้กลับมาตั้งตรง! (และขยายขอบภาพเพื่อไม่ให้ส่วนไหนขาดหาย)
                st.info(f"Detected rotation, rotating image by -{angle_to_rotate} degrees...")
                return rgb_img.rotate(-angle_to_rotate, expand=True)
    except pytesseract.TesseractError:
        # หาก OSD ตรวจสอบไม่ได้ (ภาพเล็กหรือว่าง) ให้ใช้ภาพเดิม
        pass
    return rgb_img

# --- 3. ฟังก์ชันสมอง (OCR Logic) ---
def extract_text_from_file(file):
    if file.type == "application/pdf":
        # ถ้าเป็น PDF โค้ชจะใช้ไลบรารีพิเศษอ่าน (เพราะ PDF เอียงได้ยากกว่ารูปถ่าย)
        import pdfplumber
        text = ""
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    else:
        # ถ้าเป็นรูปภาพ หรือภาพถ่ายจากกล้อง
        img = Image.open(file)
        
        # 🎯 ขั้นตอนสำคัญ: แก้ไขภาพเอียงก่อนอ่าน!
        deskewed_img = image_deskewing(img)
        
        # ใช้วิธี psm 3 เพื่อให้อ่านข้อความกระจายตัวบนแปลนได้ดีขึ้น
        return pytesseract.image_to_string(deskewed_img, lang='tha+eng', config='--psm 3')

def process_pea_codes(full_text, suffix_target):
    summary = {}
    
    # regex ดึงรหัสก่อนวงเล็บ สัญลักษณ์เหมือน Apps Script เป๊ะ
    inner_text = re.search(r'\((.*?)\)', suffix_target)
    suffix_for_regex = inner_text.group(1).strip() if inner_text else suffix_target.strip()
    
    regex_str = r"([a-zA-Z0-9\-\.\s]+)\s*\(\s*" + re.escape(suffix_for_regex) + r"\s*\)"
    
    matches = re.finditer(regex_str, full_text, re.IGNORECASE)
    
    for match in matches:
        raw_code = match.group(1).strip().upper()
        clean_code = re.sub(r'\s+', '', raw_code)
        
        # ซ่อมรหัสที่ OCR มักอ่านผิด
        clean_code = re.sub(r'^88-', '8-', clean_code)
        if clean_code == '88': clean_code = '8'
        
        if len(clean_code) > 0:
            final_code = f"{clean_code}({suffix_for_regex.upper()})"
            summary[final_code] = summary.get(final_code, 0) + 1
    return summary

# --- 4. ส่วนหน้าจอ UI ---
st.markdown("""<div style="background: linear-gradient(135deg, #622181, #9d308d); color: white; padding: 20px; text-align: center; border-radius: 20px 20px 0 0; margin: 0 -2rem 2rem -2rem;"><h2 style="margin: 0; color: white; font-size: 20px;">💜 โปรแกรมประมวลผลแปลน ผบส. (V.แก้ภาพเอียง)</h2></div>""", unsafe_allow_html=True)

input_mode = st.radio("ช่องทางนำเข้า:", ["อัปโหลดไฟล์/ PDF", "ถ่ายรูปจากมือถือ"], horizontal=True)

uploaded_file = None
if input_mode == "อัปโหลดไฟล์/ PDF":
    uploaded_file = st.file_uploader("เลือกไฟล์แปลน...", type=["pdf", "png", "jpg", "jpeg"])
else:
    uploaded_file = st.camera_input("ส่องไปที่รหัสในแปลนแล้วกดถ่ายรูป")

suffix = st.text_input("ค้นหารหัสที่ลงท้ายด้วย (เช่น (IN)):", value="(IN)")

if st.button("🚀 เริ่มคำนวณและประมาณการ"):
    if uploaded_file:
        with st.spinner('AI กำลังเพ่งอ่านรหัส...'):
            raw_text = extract_text_from_file(uploaded_file)
            result_dict = process_pea_codes(raw_text, suffix)
            
            if result_dict:
                st.success(f"✅ ตรวจพบรหัส {len(result_dict)} รายการ")
                
                df = pd.DataFrame(result_dict.items(), columns=['รหัสอุปกรณ์ (ตั้งตรง)', 'จำนวน'])
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button("📥 ดาวน์โหลด Excel", data=output.getvalue(), file_name="summary.xlsx")
            else:
                st.warning("🔍 ไม่พบรหัส ลองถ่ายใหม่ให้เห็นชัดๆ นะครับ")
    else:
        st.error("❌ กรุณาใส่ข้อมูลก่อน")