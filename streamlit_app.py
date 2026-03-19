import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io
from streamlit_image_coordinates import streamlit_image_coordinates

# ==========================================
# 0. 頁面基本設定與 CSS 注入
# ==========================================
st.set_page_config(page_title="環久國際機構-蓋章小工具V7.2精準中心對齊版", page_icon="📄", layout="wide")

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

if "stamp_pos" not in st.session_state:
    st.session_state.stamp_pos = None

CM_TO_PTS = 28.346 # 1公分 ≈ 28.346點 (PDF標準單位)

# ==========================================
# 1. 側邊欄 UI
# ==========================================
st.sidebar.header("⚙️ 1. 印章位置與頁面設定")
apply_mode = st.sidebar.radio("蓋章範圍", ["單頁", "全頁 (所有頁面)"])
page_num = st.sidebar.number_input("目標 / 預覽頁數", min_value=1, value=1)

st.sidebar.markdown("---")
st.sidebar.markdown("**📐 印章尺寸 (公分)**")
stamp_width_cm = st.sidebar.number_input("印章寬度 (公分)", min_value=1.0, value=3.0, step=0.1)

st.sidebar.header("🛠️ 2. 影像微調")
auto_bg_remove = st.sidebar.checkbox("✨ 自動濾除印章白底", value=True)
opacity = st.sidebar.slider("💧 印章不透明度", 0.0, 1.0, 1.0)
rotation = st.sidebar.slider("🔄 印章旋轉角度", -180, 180, 0)

if st.sidebar.button("🗑️ 清除印章重蓋"):
    st.session_state.stamp_pos = None
    st.rerun()

# ==========================================
# 2. 頂部上傳區塊
# ==========================================
col_up1, col_up2 = st.columns(2)
with col_up1:
    pdf_file = st.file_uploader("📁 1. 上傳 PDF 檔案", type=["pdf"])
with col_up2:
    stamp_file = st.file_uploader("💮 2. 上傳印章圖檔", type=["png", "jpg", "jpeg"])

# ==========================================
# 3. 主程式邏輯 (PDF渲染 + 互動點擊 + PDF匯出)
# ==========================================
if pdf_file and stamp_file:
    try:
        # --- A. 讀取並處理印章 (PIL Image) ---
        stamp_img = Image.open(stamp_file).convert("RGBA")
        
        # 1. 自動去背處理
        if auto_bg_remove:
            data = np.array(stamp_img)
            r, g, b, a = data.T
            white_areas = (r > 200) & (g > 200) & (b > 200)
            data[..., 3][white_areas.T] = 0
            stamp_img = Image.fromarray(data)

        # 2. 旋轉處理
        stamp_img = stamp_img.rotate(rotation, expand=True)
        
        # 3. 透明度處理
        if opacity < 1.0:
            alpha = stamp_img.getchannel('A')
            alpha = alpha.point(lambda p: p * opacity)
            stamp_img.putalpha(alpha)


        # --- B. 讀取 PDF 與渲染預覽圖 ---
        doc = fitz.open(stream=pdf_file.getvalue(), filetype="pdf")
        page_index = page_num - 1
        
        if page_index < 0 or page_index >= len(doc):
            st.error(f"❌ 錯誤：這份 PDF 沒有第 {page_num} 頁！(總頁數: {len(doc)})")
        else:
            page = doc[page_index]
            
            # 設定預覽圖的解析度
            max_interactive_width = 1200
            zoom = max_interactive_width / page.rect.width
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            
            # 將 PDF 頁面轉為 PIL 圖片供畫布使用
            doc_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")

            # --- C. 印章預覽尺寸換算 ---
            stamp_w_pts_initial = stamp_width_cm * CM_TO_PTS
            stamp_w_px = int(stamp_w_pts_initial * zoom)
            
            # 依比例縮放印章預覽圖
            stamp_ratio_px = stamp_w_px / stamp_img.width  
            new_size_px = (stamp_w_px, int(stamp_img.height * stamp_ratio_px))
            if new_size_px[0] > 0 and new_size_px[1] > 0:
                stamp_preview_img = stamp_img.resize(new_size_px, Image.Resampling.LANCZOS)
            else:
                stamp_preview_img = stamp_img

            # --- D. 互動預覽區 ---
            st.markdown("### 👁️ 文件預覽與蓋章區")
            st.markdown("💡 **操作方式：** 直接在下方文件點擊您想蓋章的位置（**這會是對齊印章的正中心**）。如需修改，直接點擊新的位置即可。")

            display_img = doc_img.copy()

            # ==========================================
            # 核心修復 1：預覽圖的「中心點對齊」邏輯
            # ==========================================
            if st.session_state.stamp_pos is not None:
                click_px_x, click_px_y = st.session_state.stamp_pos
                
                # 計算要貼上印章的「左上角」座標 (讓點擊位置成為中心點)
                top_left_x = int(click_px_x - (stamp_preview_img.width / 2))
                top_left_y = int(click_px_y - (stamp_preview_img.height / 2))
                
                display_img.paste(stamp_preview_img, (top_left_x, top_left_y), stamp_preview_img)

            st.markdown("<br>", unsafe_allow_html=True)
            pre_col1, pre_col2, pre_col3 = st.columns([1, 10, 1]) 

            with pre_col2:
                clicked_value = streamlit_image_coordinates(display_img, key="interactive_canvas", use_column_width=True)

            if clicked_value is not None:
                new_pos = (clicked_value["x"], clicked_value["y"])
                if st.session_state.stamp_pos != new_pos:
                    st.session_state.stamp_pos = new_pos
                    st.rerun()

            # --- E. 產生已蓋章的 PDF 供下載 ---
            if st.session_state.stamp_pos is not None:
                st.markdown("---")
                st.success("🎉 印章已定位！請點擊下方按鈕下載完成的 PDF 檔。")
                
                # ==========================================
                # 核心修復 2：PDF 物理座標的「中心點對齊」邏輯
                # ==========================================
                click_px_x, click_px_y = st.session_state.stamp_pos
                
                ratio_x = page.rect.width / pix.width
                ratio_y = page.rect.height / pix.height

                # 1. 先找出點擊位置在 PDF 上的「物理中心點座標」
                center_pdf_x = click_px_x * ratio_x
                center_pdf_y = click_px_y * ratio_y
                
                # 2. 計算印章在 PDF 中的物理尺寸 (Points)
                stamp_w_pts = stamp_width_cm * CM_TO_PTS
                stamp_aspect_ratio = stamp_img.height / stamp_img.width
                stamp_h_pts = stamp_w_pts * stamp_aspect_ratio
                
                # 3. 從中心點往回推算 PDF 的左上角座標
                pdf_top_left_x = center_pdf_x - (stamp_w_pts / 2)
                pdf_top_left_y = center_pdf_y - (stamp_h_pts / 2)
                
                # 建立 PDF 的矩形插入範圍
                rect = fitz.Rect(pdf_top_left_x, pdf_top_left_y, pdf_top_left_x + stamp_w_pts, pdf_top_left_y + stamp_h_pts)
                
                stamp_bytes_io = io.BytesIO()
                stamp_img.save(stamp_bytes_io, format="PNG")
                stamp_bytes = stamp_bytes_io.getvalue()
                
                if apply_mode == "全頁 (所有頁面)":
                    for p in doc:
                        p.insert_image(rect, stream=stamp_bytes)
                else:
                    doc[page_index].insert_image(rect, stream=stamp_bytes)
                
                output_pdf = io.BytesIO()
                doc.save(output_pdf)
                
                st.download_button(
                    label="📥 點我下載已蓋章 PDF",
                    data=output_pdf.getvalue(),
                    file_name=f"已蓋章_{pdf_file.name}",
                    mime="application/pdf",
                    type="primary"
                )

    except Exception as e:
        st.error(f"發生錯誤：{e}")

else:
    st.info("請先在上方上傳「PDF 文件」與「印章」圖檔。")
