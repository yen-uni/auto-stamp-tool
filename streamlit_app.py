import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io
from streamlit_cropper import st_cropper

st.set_page_config(page_title="環久國際機構-蓋章小工具V7極速版 (對照增強)", page_icon="📄", layout="wide")

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
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        data = np.array(img)
        
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
        # 旋轉後再次裁切確保尺寸精準
        bbox2 = img.getbbox()
        if bbox2:
            img = img.crop(bbox2)
            
    return img

st.title("📄 環久國際機構-蓋章小工具V7極速版")
st.markdown("請先上傳檔案，接著**在預覽圖上拖曳紅框**決定印章位置，右側可調尺寸。如需精準對照，請上傳「已用印樣板」。")

# --- 檔案上傳區 ---
col_upload1, col_upload2, col_upload3 = st.columns(3) # 【新增校對邏輯】增加一個上傳欄位
with col_upload1:
    pdf_file = st.file_uploader("📁 1. 上傳空白 PDF 檔案", type=["pdf"])
with col_upload2:
    stamp_file = st.file_uploader("💮 2. 上傳印章圖檔", type=["png", "jpg", "jpeg"])
with col_upload3: # 【新增校對邏輯】
    ref_pdf_file = st.file_uploader("📁 3. (選填) 上傳已蓋章參考 PDF (對照用)", type=["pdf"])

if pdf_file and stamp_file:
    st.markdown("---")
    
    # --- 讀取 PDF 並產生目標背景圖 ---
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    
    # 側邊欄：頁面設定
    st.sidebar.header("⚙️ 1. 蓋章頁面設定")
    apply_mode = st.sidebar.radio("蓋章範圍", ["單頁", "全頁 (所有頁面)"])
    page_num = st.sidebar.number_input("目標 / 預覽頁數", min_value=1, max_value=len(doc), value=1)
    page_index = page_num - 1
    
    # 抓取該頁影像 (使用標準 72 DPI 定位用)
    target_page = doc[page_index]
    pix = target_page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
    pdf_bg_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # --- 主畫面分為左右兩欄 ---
    col_main1, col_main2 = st.columns([1.2, 1])
    
    with col_main1:
        st.write("### 📍 步驟一：拖曳紅框決定位置")
        st.info("提示：移動紅框左上角到目標位置。紅框大小不影響，實際印章大小請由右側設定。")
        
        box_coords = st_cropper(
            pdf_bg_img, 
            aspect_ratio=None, 
            box_color='#FF0000',
            return_type='box',
            key='stamp_positioner'
        )
        
        x_pos = box_coords['left']
        y_pos = box_coords['top']
        
    with col_main2:
        # --- 側邊欄：校對對照設定 【新增校對邏輯】 ---
        st.sidebar.markdown("---")
        st.sidebar.header("👁️ 校對對照設定")
        
        # 即使沒上傳參考檔也可設定透明度
        overlay_opacity = st.sidebar.slider(
            "對照樣板透明度", 
            min_value=0.0, 
            max_value=1.0, 
            value=0.5, 
            step=0.05,
            help="調整上傳的樣板PDF與空白PDF的混合比例，以便對準。"
        )

        # 側邊欄：實體尺寸與影像微調 (原本邏輯，保留)
        st.sidebar.markdown("---")
        st.sidebar.markdown("**📐 印章實際列印尺寸 (公分)**")
        stamp_w_cm = st.sidebar.number_input("印章寬度 (公分)", value=3.00, min_value=0.10, max_value=20.00, step=0.10, format="%.2f")
        stamp_w = stamp_w_cm * CM_TO_PTS
        
        st.sidebar.header("🛠️ 2. 影像微調")
        stamp_opacity = st.sidebar.slider("💧 印章不透明度", 0.1, 1.0, 1.0, 0.05)
        auto_bg_remove = st.sidebar.checkbox("✨ 自動濾除印章白底", value=True)
        flip_horizontal = st.sidebar.checkbox("↔️ 水平翻轉", value=False)
        flip_vertical = st.sidebar.checkbox("↕️ 垂直翻轉", value=False)
        rotation_angle = st.sidebar.select_slider("🔄 印章旋轉角度", options=[0, 90, 180, 270, 360], value=0)
        
        # --- 處理印章並準備蓋章數據 ---
        stamp_file.seek(0)
        final_stamp = process_stamp(stamp_file, auto_bg_remove, flip_horizontal, flip_vertical, rotation_angle, stamp_opacity)
        
        stamp_bytes_io = io.BytesIO()
        final_stamp.save(stamp_bytes_io, format="PNG")
        stamp_bytes = stamp_bytes_io.getvalue()
        
        pillow_ratio = final_stamp.width / final_stamp.height
        dynamic_rect_h = stamp_w / pillow_ratio
        rect = fitz.Rect(x_pos, y_pos, x_pos + stamp_w, y_pos + dynamic_rect_h)
        
        # 依照模式插入圖片 (這步是在記憶體中修改 PDF 資料)
        if apply_mode == "全頁 (所有頁面)":
            for p in doc:
                p.insert_image(rect, stream=stamp_bytes)
        else:
            target_page.insert_image(rect, stream=stamp_bytes)
            
        # ================================================================
        # --- 產生預覽圖 (整合校對對照邏輯) 【新增/修改核心邏輯】 ---
        # ================================================================
        st.write("### 👁️ 步驟二：即時高畫質預覽與對照")
        
        # 1. 產生空白 PDF 加上「數位新印章」的高畫質預覽 (2.0 Zoom)
        zoom_matrix = fitz.Matrix(2.0, 2.0) 
        preview_pix = target_page.get_pixmap(matrix=zoom_matrix)
        img_new = Image.frombytes("RGB", [preview_pix.width, preview_pix.height], preview_pix.samples).convert("RGBA")
        
        # 2. 如果使用者有上傳「參考對照 PDF」
        if ref_pdf_file:
            ref_doc = fitz.open(stream=ref_pdf_file.read(), filetype="pdf")
            if len(ref_doc) < page_num:
                st.warning(f"參考樣板 PDF 頁數只有 {len(ref_doc)} 頁，不足以顯示第 {page_num} 頁供對照。")
                final_display_img = img_new # 頁數不符，顯示原本預覽
            else:
                # 抓取參考頁面影像 (必須使用完全相同的 matrix 來確保實體尺寸比例一致)
                ref_target_page = ref_doc[page_index]
                ref_pix = ref_target_page.get_pixmap(matrix=zoom_matrix)
                img_ref = Image.frombytes("RGB", [ref_pix.width, ref_pix.height], ref_pix.samples).convert("RGBA")
                
                # 檢查兩張圖尺寸是否一致 (理論上來自 PyMuPDF rendering 應一致，除非文件本身尺寸不一)
                if img_new.size == img_ref.size:
                    # 進行圖像混合 (Image Blend) - 讓新印章透視到舊印章的位置
                    # 混合公式: out = image1 * (1.0 - alpha) + image2 * alpha
                    # 如果使用者滑桿設為 1.0，就只顯示參考樣板圖。預設 0.5。
                    final_display_img = Image.blend(img_new, img_ref, overlay_opacity)
                    st.caption(f"提示：目前正在與「{ref_pdf_file.name}」第 {page_num} 頁對照。調整側邊欄透明度滑桿可清楚對準。")
                else:
                    st.error("空白 PDF 與參考樣板的頁面物理尺寸不符，無法進行精準疊加對照。")
                    final_display_img = img_new
        else:
            final_display_img = img_new # 沒上傳參考檔，顯示原本預覽
        
        # 顯示最終預覽圖 (改用高畫質對照圖)
        st.image(final_display_img, caption=f"第 {page_num} 頁蓋章校對畫面 (1 pixel = 0.5 PDF點)", use_container_width=True)
        # ================================================================
        
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
