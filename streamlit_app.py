import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io

# ==========================================
# 0. 頁面基本設定
# ==========================================
st.set_page_config(page_title="環久國際機構-蓋章小工具V8精準拖曳版", page_icon="📄", layout="wide")

CM_TO_PTS = 28.346 # 1公分 ≈ 28.346點 (PDF標準單位)

# ==========================================
# 1. 側邊欄 UI (座標滑桿與設定)
# ==========================================
st.sidebar.header("⚙️ 1. 印章位置與頁面設定")
apply_mode = st.sidebar.radio("蓋章範圍", ["單頁", "全頁 (所有頁面)"])
page_num = st.sidebar.number_input("目標 / 預覽頁數", min_value=1, value=1)

st.sidebar.markdown("---")
st.sidebar.markdown("**📍 印章座標位置 (公分)**")
st.sidebar.caption("提示：可直接拖曳滑桿移動印章，或點擊數字輸入精確數值。")
# 升級為 Slider，提供「拖曳」的手感，同時具備數字輸入的精準度
x_pos_cm = st.sidebar.slider("↔️ X座標 (左右平移)", min_value=0.00, max_value=21.00, value=14.00, step=0.05, format="%.2f")
y_pos_cm = st.sidebar.slider("↕️ Y座標 (上下平移)", min_value=0.00, max_value=29.70, value=6.00, step=0.05, format="%.2f")

st.sidebar.markdown("---")
st.sidebar.markdown("**📐 印章尺寸 (公分)**")
stamp_width_cm = st.sidebar.number_input("印章寬度 (公分)", min_value=1.0, value=3.0, step=0.1)

st.sidebar.header("🛠️ 2. 影像微調")
auto_bg_remove = st.sidebar.checkbox("✨ 自動濾除印章白底", value=True)
opacity = st.sidebar.slider("💧 印章不透明度", 0.0, 1.0, 1.0)
rotation = st.sidebar.slider("🔄 印章旋轉角度", -180, 180, 0)

# ==========================================
# 2. 頂部上傳區塊
# ==========================================
col_up1, col_up2 = st.columns(2)
with col_up1:
    pdf_file = st.file_uploader("📁 1. 上傳 PDF 檔案", type=["pdf"])
with col_up2:
    stamp_file = st.file_uploader("💮 2. 上傳印章圖檔", type=["png", "jpg", "jpeg"])

# ==========================================
# 3. 主程式邏輯 (座標換算 + 即時預覽 + PDF匯出)
# ==========================================
if pdf_file and stamp_file:
    try:
        # --- A. 讀取並處理印章 (PIL Image) ---
        stamp_img = Image.open(stamp_file).convert("RGBA")
        
        if auto_bg_remove:
            data = np.array(stamp_img)
            r, g, b, a = data.T
            white_areas = (r > 200) & (g > 200) & (b > 200)
            data[..., 3][white_areas.T] = 0
            stamp_img = Image.fromarray(data)

        stamp_img = stamp_img.rotate(rotation, expand=True)
        
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
            
            # 設定預覽圖解析度
            max_interactive_width = 1200
            zoom = max_interactive_width / page.rect.width
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            doc_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")

            # --- C. 座標與尺寸換算 (絕對精準邏輯) ---
            # 1. 換算印章物理尺寸 (Points)
            stamp_w_pts = stamp_width_cm * CM_TO_PTS
            stamp_aspect_ratio = stamp_img.height / stamp_img.width
            stamp_h_pts = stamp_w_pts * stamp_aspect_ratio

            # 2. 換算預覽圖上的像素尺寸與位置
            stamp_w_px = int(stamp_w_pts * zoom)
            stamp_h_px = int(stamp_h_pts * zoom)
            px_x = int(x_pos_cm * CM_TO_PTS * zoom)
            px_y = int(y_pos_cm * CM_TO_PTS * zoom)
            
            # 縮放預覽印章
            if stamp_w_px > 0 and stamp_h_px > 0:
                stamp_preview_img = stamp_img.resize((stamp_w_px, stamp_h_px), Image.Resampling.LANCZOS)
            else:
                stamp_preview_img = stamp_img

            # --- D. 即時預覽區 ---
            st.markdown("### 👁️ 蓋章即時預覽")
            st.markdown("💡 **操作提示：** 拖動左側的 **X / Y 座標滑桿**，下方的印章就會跟著移動。")

            # 將印章精準貼在指定的像素座標上
            display_img = doc_img.copy()
            display_img.paste(stamp_preview_img, (px_x, px_y), stamp_preview_img)

            st.markdown("<br>", unsafe_allow_html=True)
            pre_col1, pre_col2, pre_col3 = st.columns([1, 10, 1]) 
            with pre_col2:
                # 單純顯示圖片，不再掛載點擊功能
                st.image(display_img, use_container_width=True)

            # --- E. 產生已蓋章的 PDF 供下載 ---
            st.markdown("---")
            st.success("🎉 確認預覽位置無誤後，請點擊下方按鈕下載高畫質 PDF 檔。")
            
            # 建立 PDF 的矩形插入範圍 (使用最原始、精準的 Points)
            pdf_x = x_pos_cm * CM_TO_PTS
            pdf_y = y_pos_cm * CM_TO_PTS
            rect = fitz.Rect(pdf_x, pdf_y, pdf_x + stamp_w_pts, pdf_y + stamp_h_pts)
            
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
