import streamlit as st
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates

# ==========================================
# 0. 頁面基本設定與 CSS 注入
# ==========================================
st.set_page_config(layout="wide", page_title="文件自動蓋章工具")

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

# 初始化 Session State 來穩定儲存座標
if "stamp_pos" not in st.session_state:
    st.session_state.stamp_pos = None

# ==========================================
# 1. 側邊欄 UI
# ==========================================
st.sidebar.title("⚙️ 1. 頁面設定")
stamp_width_cm = st.sidebar.number_input("印章寬度 (公分)", min_value=1.0, value=3.0, step=0.1)

st.sidebar.title("🛠️ 2. 影像微調")
opacity = st.sidebar.slider("印章不透明度", 0.0, 1.0, 1.0)
rotation = st.sidebar.slider("印章旋轉角度", -180, 180, 0)

# 增加一個清除印章的按鈕，防呆設計
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
# 3. 主程式邏輯 (單一畫面整合版)
# ==========================================
if doc_file and stamp_file:
    # 轉為 RGBA 支援透明度
    doc_img = Image.open(doc_file).convert("RGBA")
    stamp_img = Image.open(stamp_file).convert("RGBA")

    # 效能優化：限制文件最大寬度，避免點擊處理過載導致卡頓
    max_width = 1600
    if doc_img.width > max_width:
        ratio = max_width / doc_img.width
        new_h = int(doc_img.height * ratio)
        doc_img = doc_img.resize((max_width, new_h), Image.Resampling.LANCZOS)

    # --- 印章前處理 (大小、旋轉、透明度) ---
    # 假設 1 公分大約對應 38 像素 (一般螢幕 96 DPI 換算)
    pixel_per_cm = 38 
    target_width_px = int(stamp_width_cm * pixel_per_cm)
    stamp_ratio = target_width_px / stamp_img.width  
    new_size = (target_width_px, int(stamp_img.height * stamp_ratio))
    
    if new_size[0] > 0 and new_size[1] > 0:
        stamp_img = stamp_img.resize(new_size, Image.Resampling.LANCZOS)
    
    # 旋轉
    stamp_img = stamp_img.rotate(rotation, expand=True)
    
    # 透明度處理 (更乾淨的寫法)
    if opacity < 1.0:
        alpha = stamp_img.getchannel('A')
        alpha = alpha.point(lambda p: p * opacity)
        stamp_img.putalpha(alpha)

    # --- 單一互動預覽區 ---
    st.markdown("### 👁️ 文件預覽與蓋章區")
    st.markdown("💡 **操作方式：** 直接在下方文件點擊您想蓋章的位置。如需修改，直接點擊**新的位置**，或調整左側數值即可。")

    # 複製一份準備顯示與合成的圖片
    display_img = doc_img.copy()

    # 如果已經有座標紀錄，就把印章合成上去
    if st.session_state.stamp_pos is not None:
        x, y = st.session_state.stamp_pos
        display_img.paste(stamp_img, (x, y), stamp_img)

    # 顯示這張「可能已經蓋好章」的圖片，並持續監聽點擊
    # 使用 use_column_width=True 讓圖片滿版顯示
    clicked_value = streamlit_image_coordinates(display_img, key="interactive_canvas", use_column_width=True)

    # 如果偵測到點擊，且座標改變了，就更新狀態並強制畫面重整
    if clicked_value is not None:
        new_pos = (clicked_value["x"], clicked_value["y"])
        if st.session_state.stamp_pos != new_pos:
            st.session_state.stamp_pos = new_pos
            st.rerun() # 關鍵：瞬間重新整理，讓印章馬上出現在新位置

else:
    st.info("請先在上方上傳「文件」與「印章」檔案。")
