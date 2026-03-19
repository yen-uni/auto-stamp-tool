import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io
from streamlit_image_coordinates import streamlit_image_coordinates

# 1. 網頁基本設定
st.set_page_config(page_title="環久國際機構-蓋章小工具V9點擊顯示優化版", page_icon="📄", layout="wide")

# 將公分轉換為 PyMuPDF 支援的「點 (Points)」(1 公分 ≈ 28.346 點)
CM_TO_PTS = 28.346

# 🆕 **🆕 Request 1: 注入 CSS，強制在文件區域顯示 Crosshair 十字游標 🆕** 🆕
st.markdown("""
<style>
/* 強制在點擊定位器圖片上方顯示 crosshair 十字 (精準定位) 游標 */
div.st-image-coordinates > img {
    cursor: crosshair !important;
}
</style>
""", unsafe_allow_html=True)

# --- 影像處理函式 (包含自動裁切透明邊界，確保尺寸精準) ---
def process_stamp(img_file, remove_bg, flip_h, flip_v, rotation_angle, opacity):
    # 讀取圖片並轉為 RGBA
    img = Image.open(img_file).convert("RGBA")
    
    # 1. 自動去背處理 (濾除白色背景)
    if remove_bg:
        data = np.array(img)
        r, g, b, a = data.T
        white_areas = (r > 200) & (g > 200) & (b > 200)
        data[..., 3][white_areas.T] = 0
        img = Image.fromarray(data)
    
    # 2. 自動裁切透明邊界 (確保輸入的公分是「印章圖案本身」的大小)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        
    # 3. 透明度調整
    if opacity < 1.0:
        data = np.array(img)
        data[..., 3] = (data[..., 3] * opacity).astype(np.uint8)
        img = Image.fromarray(data)
        
    # 4. 鏡像翻轉處理
    if flip_h:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip_v:
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    
    # 5. 旋轉處理
    if rotation_angle != 0:
        img = img.rotate(rotation_angle, expand=True)
        # 旋轉後再次裁切透明邊緣
        bbox2 = img.getbbox()
        if bbox2:
            img = img.crop(bbox2)
            
    return img

# --- 網頁主標題 ---
st.title("📄 環久國際機構-蓋章小工具V9點擊顯示優化版")
st.markdown("只需上傳 PDF 與印章，**直接在左側畫面上「點擊」你想蓋章的位置**，右側預覽會即時更新。")

# --- 檔案上傳區 ---
col_u1, col_u2 = st.columns(2)
with col_u1:
    pdf_file = st.file_uploader("📁 1. 上傳 PDF 檔案", type=["pdf"])
with col_u2:
    stamp_file = st.file_uploader("💮 2. 上傳印章圖檔", type=["png", "jpg", "jpeg"])

# --- 主要作業邏輯 ---
if pdf_file and stamp_file:
    st.markdown("---")
    
    # 讀取 PDF
    pdf_stream = pdf_file.read()
    doc = fitz.open(stream=pdf_stream, filetype="pdf")
    
    # --- 左側設定選單 ---
    st.sidebar.header("⚙️ 1. 頁面設定")
    apply_mode = st.sidebar.radio("蓋章範圍", ["單頁", "全頁 (所有頁面)"])
    page_num = st.sidebar.number_input("目標 / 預覽頁數", min_value=1, max_value=len(doc), value=1)
    page_index = page_num - 1
    
    # 側邊欄：尺寸設定
    st.sidebar.markdown("---")
    st.sidebar.markdown("**📐 印章實際尺寸 (公分)**")
    stamp_w_cm = st.sidebar.number_input("印章寬度 (公分)", value=3.00, min_value=0.10, max_value=20.00, step=0.10, format="%.2f")
    stamp_w = stamp_w_cm * CM_TO_PTS
    
    st.sidebar.header("🛠️ 2. 影像微調")
    stamp_opacity = st.sidebar.slider("💧 印章不透明度", 0.1, 1.0, 1.0, 0.05)
    auto_bg_remove = st.sidebar.checkbox("✨ 自動濾除印章白底", value=True)
    flip_horizontal = st.sidebar.checkbox("↔️ 水平翻轉", value=False)
    flip_vertical = st.sidebar.checkbox("↕️ 垂直翻轉", value=False)
    rotation_angle = st.sidebar.select_slider("🔄 印章旋轉角度", options=[0, 90, 180, 270, 360], value=0)

    # --- 畫面佈局：左側點擊定位，右側預覽 ---
    col_pos, col_preview = st.columns([1.2, 1])

    with col_pos:
        st.write("### 📍 步驟一：滑鼠點擊定位")
        # 🆕 **🆕 Request 1: 替換成更醒目的 HTML styled text，明確提示「十字游標」點擊定位 🆕** 🆕
        st.markdown('<p style="color:red; font-size:22px; font-weight:bold;">🚨 重要提示：不需要拖曳了！</p>', unsafe_allow_html=True)
        st.markdown('<p style="font-size:18px; margin-bottom:20px;">請將滑鼠移到下方文件影像上（游標會變成 **十字線**），然後直接**「點擊」**你想蓋章的位置（這會是印章的左上角）。請點點看！</p>', unsafe_allow_html=True)
        
        # 獲取該頁底圖 (1.0 縮放確保 1px = 1pt)
        target_page = doc[page_index]
        pix = target_page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
        pdf_bg_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # 點擊定位組件
        coords = streamlit_image_coordinates(pdf_bg_img, key="stamp_positioner")
        
        # 取得點擊的座標 (如果還沒點擊，預設放在左上角)
        if coords is not None:
            x_pos = coords['x']
            y_pos = coords['y']
        else:
            x_pos = 150
            y_pos = 150

    with col_preview:
        st.write("### 👁️ 步驟二：即時預覽")
        
        try:
            # 1. 處理印章圖檔
            stamp_file.seek(0)
            processed_stamp_img = process_stamp(stamp_file, auto_bg_remove, flip_horizontal, flip_vertical, rotation_angle, stamp_opacity)
            
            # 轉換為位元組供 PyMuPDF 使用
            stamp_buffer = io.BytesIO()
            processed_stamp_img.save(stamp_buffer, format="PNG")
            stamp_bytes = stamp_buffer.getvalue()
            
            # 2. 計算比例與高度 (單位均為點)
            pillow_ratio = processed_stamp_img.width / processed_stamp_img.height
            dynamic_rect_h = stamp_w / pillow_ratio
            rect = fitz.Rect(x_pos, y_pos, x_pos + stamp_w, y_pos + dynamic_rect_h)
            
            # 3. 執行蓋章 (僅用於產生網頁預覽)
            if apply_mode == "全頁 (所有頁面)":
                for p in doc:
                    p.insert_image(rect, stream=stamp_bytes)
            else:
                target_page.insert_image(rect, stream=stamp_bytes)
            
            # 🆕 **🆕 Request 2: 產生「標準解析度」網頁顯示預覽圖 (1.0 縮放) 🆕** 🆕
            # 這樣步驟二預覽圖的大小會跟步驟一完全一樣，避免混淆。此處只影響網頁顯示，不影響下載品質。
            standard_zoom_matrix = fitz.Matrix(1.0, 1.0) 
            display_pix = target_page.get_pixmap(matrix=standard_zoom_matrix)
            img_display = Image.frombytes("RGB", [display_pix.width, display_pix.height], display_pix.samples)
            
            # 顯示與步驟一同大小的預覽圖
            st.image(img_display, caption=f"第 {page_num} 頁蓋章結果 (顯示大小與點擊區域同步)", use_container_width=True)
            
            # --- 以下為 PDF 下載專用的高解析度處理 (在下載時重新打開乾淨文件處理，確保品質) ---
            # 當使用者下載時，才讀取 PDF stream 產生一個乾淨的 doc 用於最終產出
            download_doc = fitz.open(stream=pdf_stream, filetype="pdf")
            
            # rect 的單位是 points，PyMuPDF 會自動處理 scaling，只需在乾淨文件上重新蓋章
            if apply_mode == "全頁 (所有頁面)":
                for p in download_doc:
                    p.insert_image(rect, stream=stamp_bytes)
            else:
                download_target_page = download_doc[page_index]
                download_target_page.insert_image(rect, stream=stamp_bytes)
            
            output_pdf = io.BytesIO()
            # 使用 defalte 和 linear 參數優化 PDF，並保留原始解析度矩陣
            download_doc.save(output_pdf, deflate=True)
            
            # 成功訊息與下載按鈕
            st.success("🎉 預覽無誤後，即可點擊下方下載高解析度完成檔")
            st.download_button(
                label="📥 下載已蓋章 PDF",
                data=output_pdf.getvalue(),
                file_name=f"已蓋章_{pdf_file.name}",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
            
        except Exception as e:
            st.error(f"預覽生成失敗：{e}")

st.markdown("---")
st.markdown("© 2026 環久國際開發有限公司人力文件處理系統 | 用滑鼠「點點看」吧！🛑")
