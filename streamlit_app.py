import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io
from streamlit_cropper import st_cropper

st.set_page_config(page_title="環久國際機構-蓋章小工具V7極速版", page_icon="📄", layout="wide")

# 將公分轉換為 PyMuPDF 支援的「點 (Points)」(1 公分 ≈ 28.346 點)
CM_TO_PTS = 28.346

def process_stamp(img_file, remove_bg, flip_h, flip_v, rotation_angle, opacity):
    # 讀取圖片並轉為 RGBA
    img = Image.open(img_file).convert("RGBA")
    data = np.array(img)
    
    # 1. 自動去背處理
    if remove_bg:
        r, g, b, a = data.T
        white_areas = (r > 200) & (g > 200) & (b > 200)
        data[..., 3][white_areas.T] = 0
        img = Image.fromarray(data)
    
    # 2. 自動裁切透明邊界 (這步是解決「實際尺寸不符」的關鍵！)
    # 取得圖片中非透明區域的邊界框，並將多餘的透明像素裁掉
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        data = np.array(img) # 重新轉換為陣列以處理透明度
        
    # 3. 透明度調整
    if opacity < 1.0:
        data[..., 3] = (data[..., 3] * opacity).astype(np.uint8)
        img = Image.fromarray(data)
        
    # 4. 鏡像與翻轉
    if flip_h:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip_v:
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        
    # 5. 旋轉處理
    if rotation_angle != 0:
        img = img.rotate(rotation_angle, expand=True)
        # 旋轉後可能會產生新的透明邊緣，再次裁切確保尺寸精準
        bbox2 = img.getbbox()
        if bbox2:
            img = img.crop(bbox2)
            
    return img

st.title("📄 環久國際機構-蓋章小工具V7極速版")
st.markdown("請先上傳檔案，接著**在預覽圖上拖曳紅框**決定印章左上角位置，右側可微調真實大小！")

# --- 檔案上傳區 (移到最上方，有檔案才顯示後續設定) ---
col_upload1, col_upload2 = st.columns(2)
with col_upload1:
    pdf_file = st.file_uploader("📁 1. 上傳 PDF 檔案", type=["pdf"])
with col_upload2:
    stamp_file = st.file_uploader("💮 2. 上傳印章圖檔", type=["png", "jpg", "jpeg"])

if pdf_file and stamp_file:
    st.markdown("---")
    
    # --- 讀取 PDF 並產生第一頁的背景圖供定位使用 ---
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    
    # 側邊欄：頁面設定
    st.sidebar.header("⚙️ 1. 蓋章頁面設定")
    apply_mode = st.sidebar.radio("蓋章範圍", ["單頁", "全頁 (所有頁面)"])
    page_num = st.sidebar.number_input("目標 / 預覽頁數", min_value=1, max_value=len(doc), value=1)
    page_index = page_num - 1
    
    # 抓取該頁影像 (使用 72 DPI，這樣 1 像素剛好等於 PDF 的 1 點，座標轉換最精準)
    target_page = doc[page_index]
    pix = target_page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
    pdf_bg_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # --- 主畫面分為左右兩欄：左邊拖曳定位，右邊預覽與下載 ---
    col_main1, col_main2 = st.columns([1.2, 1])
    
    with col_main1:
        st.write("### 📍 步驟一：拖曳紅框決定位置")
        st.info("提示：只需要移動紅框的**左上角**到你要蓋章的位置即可。紅框大小不影響，印章實際大小請由側邊欄設定。")
        
        # 使用 cropper 但只取座標 (return_type='box')
        box_coords = st_cropper(
            pdf_bg_img, 
            aspect_ratio=None, 
            box_color='#FF0000',
            return_type='box',  # 關鍵：不回傳圖片，只回傳座標字典
            key='stamp_positioner'
        )
        
        # 轉換座標：cropper 回傳的是 pixel，但在我們的設定下 1 pixel = 1 point
        x_pos = box_coords['left']
        y_pos = box_coords['top']
        
    with col_main2:
        # 側邊欄：實體尺寸設定
        st.sidebar.markdown("---")
        st.sidebar.markdown("**📐 印章實際列印尺寸 (公分)**")
        st.sidebar.caption("提示：系統已自動裁去印章圖檔的透明邊緣，請直接輸入實體印章大小。")
        stamp_w_cm = st.sidebar.number_input("印章寬度 (公分)", value=3.00, min_value=0.10, max_value=20.00, step=0.10, format="%.2f")
        stamp_w = stamp_w_cm * CM_TO_PTS
        
        # 側邊欄：影像微調
        st.sidebar.header("🛠️ 2. 影像微調")
        stamp_opacity = st.sidebar.slider("💧 印章不透明度", 0.1, 1.0, 1.0, 0.05)
        auto_bg_remove = st.sidebar.checkbox("✨ 自動濾除印章白底", value=True)
        flip_horizontal = st.sidebar.checkbox("↔️ 水平翻轉", value=False)
        flip_vertical = st.sidebar.checkbox("↕️ 垂直翻轉", value=False)
        rotation_angle = st.sidebar.select_slider("🔄 印章旋轉角度", options=[0, 90, 180, 270, 360], value=0)
        
        # --- 處理印章並蓋上 PDF ---
        stamp_file.seek(0)
        final_stamp = process_stamp(stamp_file, auto_bg_remove, flip_horizontal, flip_vertical, rotation_angle, stamp_opacity)
        
        stamp_bytes_io = io.BytesIO()
        final_stamp.save(stamp_bytes_io, format="PNG")
        stamp_bytes = stamp_bytes_io.getvalue()
        
        # 依照處理完的印章長寬比，動態計算高度
        pillow_ratio = final_stamp.width / final_stamp.height
        dynamic_rect_h = stamp_w / pillow_ratio
        
        # 定義蓋章區域 (X與Y來自拖曳框，寬高來自側邊欄公分換算)
        rect = fitz.Rect(x_pos, y_pos, x_pos + stamp_w, y_pos + dynamic_rect_h)
        
        # 執行蓋章
        if apply_mode == "全頁 (所有頁面)":
            for p in doc:
                p.insert_image(rect, stream=stamp_bytes)
        else:
            target_page.insert_image(rect, stream=stamp_bytes)
            
        # 產生高畫質預覽圖
        st.write("### 👁️ 步驟二：即時高畫質預覽")
        zoom_matrix = fitz.Matrix(2.0, 2.0) 
        preview_pix = target_page.get_pixmap(matrix=zoom_matrix)
        img_preview = Image.frombytes("RGB", [preview_pix.width, preview_pix.height], preview_pix.samples)
        
        st.image(img_preview, caption=f"第 {page_num} 頁蓋章結果", use_container_width=True)
        
        # 提供下載
        output_pdf = io.BytesIO()
        doc.save(output_pdf)
        
        st.success("🎉 預覽無誤後即可下載！")
        st.download_button(
            label="📥 點我下載已蓋章 PDF",
            data=output_pdf.getvalue(),
            file_name=f"已蓋章_{pdf_file.name}",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
