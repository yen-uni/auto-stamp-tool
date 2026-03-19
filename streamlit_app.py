import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io
from streamlit_image_coordinates import streamlit_image_coordinates

# ==========================================
# 0. 頁面基本設定與 CSS 注入
# ==========================================
st.set_page_config(page_title="環久國際機構-蓋章小工具V7互動版", page_icon="📄", layout="wide")

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
# 1. 側邊欄 UI (完美融合 V6 選項與微調功能)
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
    # 這裡改回只接受 PDF
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
        # 使用 getvalue() 避免 Streamlit 重複讀取指標問題
        doc = fitz.open(stream=pdf_file.getvalue(), filetype="pdf")
        page_index = page_num - 1
        
        if page_index < 0 or page_index >= len(doc):
            st.error(f"❌ 錯誤：這份 PDF 沒有第 {page_num} 頁！(總頁數: {len(doc)})")
        else:
            page = doc[page_index]
            
            # 設定預覽圖的解析度 (計算 zoom 以符合約 1200px 寬度，兼顧畫質與效能)
            max_interactive_width = 1200
            zoom = max_interactive_width / page.rect.width
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            
            # 將 PDF 頁面轉為 PIL 圖片供畫布使用
            doc_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")

            # --- C. 印章尺寸換算 ---
            # 計算印章在 PDF 真實尺寸 (Points) 與 螢幕預覽尺寸 (Pixels)
            stamp_w_pts = stamp_width_cm * CM_TO_PTS
            stamp_w_px = int(stamp_w_pts * zoom)
            
            # 依比例縮放印章預覽圖
            stamp_ratio = stamp_w_px / stamp_img.width  
            new_size = (stamp_w_px, int(stamp_img.height * stamp_ratio))
            if new_size[0] > 0 and new_size[1] > 0:
                stamp_img = stamp_img.resize(new_size, Image.Resampling.LANCZOS)

            # --- D. 互動預覽區 ---
            st.markdown("### 👁️ 文件預覽與蓋章區")
            st.markdown("💡 **操作方式：** 直接在下方文件點擊您想蓋章的位置（游標為十字線）。如需修改，直接點擊**新的位置**即可。")

            display_img = doc_img.copy()

            # 如果已經有座標紀錄，就在「預覽圖」上合成印章
            if st.session_state.stamp_pos is not None:
                px_x, px_y = st.session_state.stamp_pos
                display_img.paste(stamp_img, (px_x, px_y), stamp_img)

            # 版面控制：置中顯示，寬度稍微縮小視覺佔比
            st.markdown("<br>", unsafe_allow_html=True)
            pre_col1, pre_col2, pre_col3 = st.columns([1, 10, 1]) 

            with pre_col2:
                # use_column_width=True 會讓圖片撐滿這 10 等分的寬度，視覺上就是縮小 80% 的感覺
                clicked_value = streamlit_image_coordinates(display_img, key="interactive_canvas", use_column_width=True)

            # 偵測點擊，更新座標
            if clicked_value is not None:
                new_pos = (clicked_value["x"], clicked_value["y"])
                if st.session_state.stamp_pos != new_pos:
                    st.session_state.stamp_pos = new_pos
                    st.rerun()

            # --- E. 產生已蓋章的 PDF 供下載 ---
            if st.session_state.stamp_pos is not None:
                st.markdown("---")
                st.success("🎉 印章已定位！請點擊下方按鈕下載完成的 PDF 檔。")
                
                # 1. 座標轉換 (Pixels -> PDF Points)
                px_x, px_y = st.session_state.stamp_pos
                pdf_x = px_x / zoom
                pdf_y = px_y / zoom
                
                # 計算印章在 PDF 中的高度
                stamp_h_pts = stamp_w_pts * (stamp_img.height / stamp_img.width)
                
                # 建立 PDF 的矩形插入範圍
                rect = fitz.Rect(pdf_x, pdf_y, pdf_x + stamp_w_pts, pdf_y + stamp_h_pts)
                
                # 2. 將處理好的印章轉為 Bytes
                stamp_bytes_io = io.BytesIO()
                stamp_img.save(stamp_bytes_io, format="PNG")
                stamp_bytes = stamp_bytes_io.getvalue()
                
                # 3. 根據選項執行蓋章
                if apply_mode == "全頁 (所有頁面)":
                    for p in doc:
                        p.insert_image(rect, stream=stamp_bytes)
                else:
                    # 單頁模式
                    doc[page_index].insert_image(rect, stream=stamp_bytes)
                
                # 4. 準備下載
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
