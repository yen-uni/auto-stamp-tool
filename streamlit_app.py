import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="環久國際機構-蓋章小工具V7互動極速版", page_icon="📄", layout="wide")

# ==========================================
# 0. CSS 游標注入與狀態初始化
# ==========================================
# 強制游標顯示為十字線
st.markdown(
    """
    <style>
    [data-testid="stImage"] img, canvas, .stImage {
        cursor: crosshair !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 初始化 Session State 來穩定儲存點擊座標
if "stamp_pos" not in st.session_state:
    st.session_state.stamp_pos = None

# 將公分轉換為 PyMuPDF 支援的「點 (Points)」(1 公分 ≈ 28.346 點)
CM_TO_PTS = 28.346

# ==========================================
# 1. 核心影像處理函式 (完全保留你原本的邏輯)
# ==========================================
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
    
    # 2. 自動裁切透明邊界 (解決「實際尺寸不符」的關鍵！)
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

st.title("📄 環久國際機構-蓋章小工具V7互動極速版")
st.markdown("請先上傳檔案，接著**在下方預覽圖上直接點擊**決定印章位置，右側側邊欄可微調真實大小！")

# ==========================================
# 2. 檔案上傳區
# ==========================================
col_upload1, col_upload2 = st.columns(2)
with col_upload1:
    pdf_file = st.file_uploader("📁 1. 上傳 PDF 檔案", type=["pdf"])
with col_upload2:
    stamp_file = st.file_uploader("💮 2. 上傳印章圖檔", type=["png", "jpg", "jpeg"])

# ==========================================
# 3. 主程式邏輯 (單一互動畫面)
# ==========================================
if pdf_file and stamp_file:
    st.markdown("---")
    
    # 讀取 PDF
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    
    # --- 側邊欄設定 ---
    st.sidebar.header("⚙️ 1. 蓋章頁面設定")
    apply_mode = st.sidebar.radio("蓋章範圍", ["單頁", "全頁 (所有頁面)"])
    page_num = st.sidebar.number_input("目標 / 預覽頁數", min_value=1, max_value=len(doc), value=1)
    page_index = page_num - 1

    st.sidebar.markdown("---")
    st.sidebar.markdown("**📐 印章實際列印尺寸 (公分)**")
    st.sidebar.caption("提示：系統已自動裁去印章圖檔的透明邊緣，請直接輸入實體印章大小。")
    stamp_w_cm = st.sidebar.number_input("印章寬度 (公分)", value=3.00, min_value=0.10, max_value=20.00, step=0.10, format="%.2f")
    stamp_w_pts = stamp_w_cm * CM_TO_PTS
    
    st.sidebar.header("🛠️ 2. 影像微調")
    stamp_opacity = st.sidebar.slider("💧 印章不透明度", 0.1, 1.0, 1.0, 0.05)
    auto_bg_remove = st.sidebar.checkbox("✨ 自動濾除印章白底", value=True)
    flip_horizontal = st.sidebar.checkbox("↔️ 水平翻轉", value=False)
    flip_vertical = st.sidebar.checkbox("↕️ 垂直翻轉", value=False)
    rotation_angle = st.sidebar.select_slider("🔄 印章旋轉角度", options=[0, 90, 180, 270, 360], value=0)
    
    if st.sidebar.button("🗑️ 清除印章重蓋"):
        st.session_state.stamp_pos = None
        st.rerun()

    # --- 處理印章 ---
    stamp_file.seek(0)
    final_stamp = process_stamp(stamp_file, auto_bg_remove, flip_horizontal, flip_vertical, rotation_angle, stamp_opacity)
    
    # 計算印章在 PDF 中的物理高度 (Points)
    pillow_ratio = final_stamp.width / final_stamp.height
    stamp_h_pts = stamp_w_pts / pillow_ratio

    # --- 產生高畫質背景圖 (保留你原本的 Matrix(2.0, 2.0)) ---
    target_page = doc[page_index]
    zoom = 2.0
    zoom_matrix = fitz.Matrix(zoom, zoom) 
    pix = target_page.get_pixmap(matrix=zoom_matrix)
    pdf_bg_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")

    # 換算印章在預覽圖上的像素大小
    preview_stamp_w = int(stamp_w_pts * zoom)
    preview_stamp_h = int(stamp_h_pts * zoom)
    
    # 調整預覽用印章大小
    if preview_stamp_w > 0 and preview_stamp_h > 0:
        preview_stamp = final_stamp.resize((preview_stamp_w, preview_stamp_h), Image.Resampling.LANCZOS)
    else:
        preview_stamp = final_stamp

    # --- 單一互動預覽區 ---
    st.markdown("### 👁️ 文件預覽與蓋章區")
    st.info("💡 **操作方式：** 直接在下方文件點擊您想蓋章的位置（這會是印章的**正中心**）。如需修改，直接點擊新的位置即可。")
    
    display_img = pdf_bg_img.copy()

    # 如果已經有點擊座標，將預覽印章貼上 (採用中心對齊以提升手感)
    if st.session_state.stamp_pos is not None:
        click_px_x, click_px_y = st.session_state.stamp_pos
        paste_x = int(click_px_x - (preview_stamp.width / 2))
        paste_y = int(click_px_y - (preview_stamp.height / 2))
        display_img.paste(preview_stamp, (paste_x, paste_y), preview_stamp)

    # 顯示可互動畫布，使用 use_column_width=True 滿版顯示
    clicked_value = streamlit_image_coordinates(display_img, key="interactive_canvas", use_column_width=True)

    # 座標更新與畫面重整
    if clicked_value is not None:
        new_pos = (clicked_value["x"], clicked_value["y"])
        if st.session_state.stamp_pos != new_pos:
            st.session_state.stamp_pos = new_pos
            st.rerun()

    # --- 蓋章寫入 PDF 與下載 ---
    if st.session_state.stamp_pos is not None:
        st.markdown("---")
        st.success("🎉 印章已定位！確認無誤後即可下載。")
        
        # 1. 座標轉換 (Pixels -> PDF Points)
        click_px_x, click_px_y = st.session_state.stamp_pos
        pdf_center_x = click_px_x / zoom
        pdf_center_y = click_px_y / zoom
        
        # 從中心點推算左上角座標
        rect_x = pdf_center_x - (stamp_w_pts / 2)
        rect_y = pdf_center_y - (stamp_h_pts / 2)
        
        # 建立 PDF 的矩形插入範圍
        rect = fitz.Rect(rect_x, rect_y, rect_x + stamp_w_pts, rect_y + stamp_h_pts)
        
        # 將最終印章轉為 Bytes
        stamp_bytes_io = io.BytesIO()
        final_stamp.save(stamp_bytes_io, format="PNG")
        stamp_bytes = stamp_bytes_io.getvalue()
        
        # 執行蓋章
        if apply_mode == "全頁 (所有頁面)":
            for p in doc:
                p.insert_image(rect, stream=stamp_bytes)
        else:
            target_page.insert_image(rect, stream=stamp_bytes)
            
        # 提供下載
        output_pdf = io.BytesIO()
        doc.save(output_pdf)
        
        st.download_button(
            label="📥 點我下載已蓋章 PDF",
            data=output_pdf.getvalue(),
            file_name=f"已蓋章_{pdf_file.name}",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )

else:
    st.info("請先在上方上傳「PDF 檔案」與「印章圖檔」。")
