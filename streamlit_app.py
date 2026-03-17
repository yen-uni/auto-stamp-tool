import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io

# 設定網頁標題與圖示
st.set_page_config(page_title="自動蓋章小工具", page_icon="📄", layout="wide")

# 將公分轉換為 PyMuPDF 支援的「點 (Points)」(1 公分 ≈ 28.346 點)
CM_TO_PTS = 28.346

# --- 影像處理函式 (包含去背、透明度與翻轉) ---
def process_stamp(img_file, remove_bg, flip_h, flip_v, opacity):
    # 讀取圖片並轉為 RGBA
    img = Image.open(img_file).convert("RGBA")
    data = np.array(img)
    
    # 1. 自動去背處理
    if remove_bg:
        r, g, b, a = data.T
        white_areas = (r > 200) & (g > 200) & (b > 200)
        data[..., 3][white_areas.T] = 0
        
    # 2. 透明度調整 (將 Alpha 通道乘上比例)
    if opacity < 1.0:
        data[..., 3] = (data[..., 3] * opacity).astype(np.uint8)
        
    img = Image.fromarray(data)
    
    # 3. 鏡像翻轉處理
    if flip_h:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip_v:
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        
    return img

# --- 網頁主要畫面 ---
st.title("📄 專屬自動蓋章小工具")
st.markdown("只需上傳 PDF 與印章，**修改左側數值，下方的預覽畫面會「即時」自動更新！**")

# --- 左側設定選單 ---
st.sidebar.header("⚙️ 1. 印章位置與頁面設定")
# 新增單頁/全頁選項
apply_mode = st.sidebar.radio("蓋章範圍", ["單頁", "全頁 (所有頁面)"])
page_num = st.sidebar.number_input("目標 / 預覽頁數", min_value=1, value=1)

# 座標設定 (改為公分)
st.sidebar.markdown("---")
st.sidebar.markdown("**📍 印章座標位置 (公分)**")
st.sidebar.caption("提示：標準 A4 紙張約為 21 寬 × 29.7 高 (公分)")

x_pos_cm = st.sidebar.number_input("X座標 (從左邊界起算, 公分)", value=14.00, min_value=0.00, max_value=100.00, step=0.01, format="%.2f")
y_pos_cm = st.sidebar.number_input("Y座標 (從上邊界起算, 公分)", value=6.00, min_value=0.00, max_value=100.00, step=0.01, format="%.2f")

# --- 新增：防呆警告機制 ---
if x_pos_cm > 21.0 or y_pos_cm > 29.7:
    st.sidebar.warning("⚠️ **注意：印章可能已超出 A4 紙張範圍！**\n\n標準 A4 寬度約 21 公分、高度約 29.7 公分。若數值過大，印章會蓋在畫面外而看不見。")
# ------------------------

x_pos = x_pos_cm * CM_TO_PTS
y_pos = y_pos_cm * CM_TO_PTS

# 尺寸設定 (公分)
st.sidebar.markdown("---")
st.sidebar.markdown("**📐 印章尺寸 (公分)**")
st.sidebar.caption("提示：一般文件印章約 2.5 ~ 4 公分")

stamp_w_cm = st.sidebar.number_input("印章寬度 (公分)", value=2.80, min_value=0.10, max_value=300.00, step=0.01, format="%.2f")
stamp_h_cm = st.sidebar.number_input("印章高度 (公分)", value=2.80, min_value=0.10, max_value=300.00, step=0.01, format="%.2f")

stamp_w = stamp_w_cm * CM_TO_PTS
stamp_h = stamp_h_cm * CM_TO_PTS

st.sidebar.header("🛠️ 2. 影像微調")
# 新增透明度滑桿
stamp_opacity = st.sidebar.slider("💧 印章不透明度", min_value=0.1, max_value=1.0, value=0.85, step=0.05, help="數值越小越透明，能透出底下的文字 (建議 0.8~0.9)")
auto_bg_remove = st.sidebar.checkbox("✨ 自動濾除印章白底", value=True)
flip_horizontal = st.sidebar.checkbox("↔️ 水平翻轉 (解決左右相反)", value=False)
flip_vertical = st.sidebar.checkbox("↕️ 垂直翻轉 (解決上下相反)", value=False)

# --- 檔案上傳區 ---
col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("📁 1. 上傳 PDF 檔案", type=["pdf"])
with col2:
    stamp_file = st.file_uploader("💮 2. 上傳印章圖檔", type=["png", "jpg", "jpeg"])

# --- 自動即時預覽與下載 ---
if pdf_file and stamp_file:
    st.markdown("---")
    
    try:
        # 確保檔案每次都在正確的讀取起點
        stamp_file.seek(0)
        pdf_file.seek(0)
        
        # 1. 處理印章圖檔 (去背 + 透明度 + 翻轉)
        final_stamp = process_stamp(stamp_file, auto_bg_remove, flip_horizontal, flip_vertical, stamp_opacity)
        stamp_bytes_io = io.BytesIO()
        final_stamp.save(stamp_bytes_io, format="PNG")
        stamp_bytes = stamp_bytes_io.getvalue()

        # 2. 處理 PDF 檔案
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        page_index = page_num - 1
        
        if page_index < 0 or page_index >= len(doc):
            st.error(f"❌ 錯誤：這份 PDF 沒有第 {page_num} 頁！(總頁數: {len(doc)})")
        else:
            # 定義印章要蓋的區塊位置
            rect = fitz.Rect(x_pos, y_pos, x_pos + stamp_w, y_pos + stamp_h)
            
            # 根據選擇的範圍執行蓋章
            if apply_mode == "全頁 (所有頁面)":
                for p in doc:
                    p.insert_image(rect, stream=stamp_bytes)
            else:
                # 單頁模式
                page = doc[page_index]
                page.insert_image(rect, stream=stamp_bytes)
            
            # 3. 產生高畫質預覽圖 (永遠只預覽選定的那一頁，避免系統卡頓)
            preview_page = doc[page_index]
            st.markdown(f"### 👁️ 蓋章即時預覽 (第 {page_num} 頁)")
            zoom_matrix = fitz.Matrix(2.0, 2.0) 
            pix = preview_page.get_pixmap(matrix=zoom_matrix)
            img_preview = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # 顯示預覽圖
            st.image(img_preview, width=600, caption="提示：修改左側任何設定，此畫面都會瞬間自動更新！")
            
            # 4. 提供下載按鈕
            output_pdf = io.BytesIO()
            doc.save(output_pdf)
            
            st.success("🎉 確認預覽無誤後，請點擊下方按鈕下載完成檔！")
            st.download_button(
                label="📥 點我下載已蓋章 PDF",
                data=output_pdf.getvalue(),
                file_name=f"已蓋章_{pdf_file.name}",
                mime="application/pdf",
                type="primary"
            )

    except Exception as e:
        st.error(f"發生錯誤：{e}")
