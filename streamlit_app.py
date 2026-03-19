import streamlit as st
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates
import numpy as np
import io

# ==========================================
# 0. 頁面基本設定與 CSS 注入
# ==========================================
st.set_page_config(layout="wide", page_title="文件自動蓋章工具 (互動+去背版)")

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

# ==========================================
# 1. 側邊欄 UI
# ==========================================
st.sidebar.title("⚙️ 1. 頁面設定")
stamp_width_cm = st.sidebar.number_input("印章寬度 (公分)", min_value=1.0, value=3.0, step=0.1)

st.sidebar.title("🛠️ 2. 影像微調")
# 將去背功能加回來
auto_bg_remove = st.sidebar.checkbox("✨ 自動濾除印章白底", value=True)
opacity = st.sidebar.slider("印章不透明度", 0.0, 1.0, 1.0)
rotation = st.sidebar.slider("印章旋轉角度", -180, 180, 0)

if st.sidebar.button("🗑️ 清除印章重蓋"):
    st.session_state.stamp_pos = None
    st.rerun()

# ==========================================
# 2. 頂部上傳區塊
# ==========================================
col_up1, col_up2 = st.columns(2)
with col_up1:
    doc_file = st.file_uploader("上傳文件檔案 (圖片格式)", type=['png', 'jpg', 'jpeg'])
with col_up2:
    stamp_file = st.file_uploader("上傳印章檔案", type=['png', 'jpg', 'jpeg'])

# ==========================================
# 3. 主程式邏輯
# ==========================================
if doc_file and stamp_file:
    # 讀取圖片並統一轉為 RGBA 支援透明度
    doc_img = Image.open(doc_file).convert("RGBA")
    stamp_img = Image.open(stamp_file).convert("RGBA")

    # --- 效能優化：限制文件寬度 ---
    max_interactive_width = 1200 
    if doc_img.width > max_interactive_width:
        ratio = max_interactive_width / doc_img.width
        new_h = int(doc_img.height * ratio)
        doc_img = doc_img.resize((max_interactive_width, new_h), Image.Resampling.LANCZOS)

    # --- 影像微調處理 ---
    # 1. 自動去背處理 (移植自 V6)
    if auto_bg_remove:
        data = np.array(stamp_img)
        r, g, b, a = data.T
        white_areas = (r > 200) & (g > 200) & (b > 200)
        data[..., 3][white_areas.T] = 0
        stamp_img = Image.fromarray(data)

    # 2. 尺寸縮放
    pixel_per_cm = 30
    target_width_px = int(stamp_width_cm * pixel_per_cm)
    stamp_ratio = target_width_px / stamp_img.width  
    new_size = (target_width_px, int(stamp_img.height * stamp_ratio))
    
    if new_size[0] > 0 and new_size[1] > 0:
        stamp_img = stamp_img.resize(new_size, Image.Resampling.LANCZOS)
    
    # 3. 旋轉處理
    stamp_img = stamp_img.rotate(rotation, expand=True)
    
    # 4. 透明度處理
    if opacity < 1.0:
        alpha = stamp_img.getchannel('A')
        alpha = alpha.point(lambda p: p * opacity)
        stamp_img.putalpha(alpha)

    # --- 單一互動預覽區 ---
    st.markdown("### 👁️ 文件預覽與蓋章區")
    st.markdown("💡 **操作方式：** 直接在下方文件點擊您想蓋章的位置（游標為十字線）。如需修改，直接點擊**新的位置**即可。")

    display_img = doc_img.copy()

    # 如果已經有座標紀錄，就把印章合成上去
    if st.session_state.stamp_pos is not None:
        x, y = st.session_state.stamp_pos
        display_img.paste(stamp_img, (x, y), stamp_img)

    st.markdown("<br>", unsafe_allow_html=True)
    pre_col1, pre_col2, pre_col3 = st.columns([1, 10, 1]) 

    with pre_col2:
        clicked_value = streamlit_image_coordinates(display_img, key="interactive_canvas", use_column_width=False)

    if clicked_value is not None:
        new_pos = (clicked_value["x"], clicked_value["y"])
        if st.session_state.stamp_pos != new_pos:
            st.session_state.stamp_pos = new_pos
            st.rerun()

    # ==========================================
    # 4. 下載區塊 (移植自 V6 並針對圖片調整)
    # ==========================================
    if st.session_state.stamp_pos is not None:
        st.markdown("---")
        st.success("🎉 印章已蓋上！確認無誤後，請點擊下方按鈕下載完成檔。")
        
        # 將 RGBA 轉回 RGB 以利存成高品質 JPG (HR 文件比較常見的格式)
        output_io = io.BytesIO()
        final_download_img = display_img.convert("RGB")
        final_download_img.save(output_io, format="JPEG", quality=95)
        
        st.download_button(
            label="📥 點我下載已蓋章文件",
            data=output_io.getvalue(),
            file_name=f"已蓋章_{doc_file.name}",
            mime="image/jpeg",
            type="primary"
        )

else:
    st.info("請先在上方上傳「文件」與「印章」檔案。")
