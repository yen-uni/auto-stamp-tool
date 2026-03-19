import streamlit as st
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates
import math # 引入 math 用於更精確的 cm 像素換算

# ==========================================
# 0. 頁面基本設定與 CSS 注入
# ==========================================
# 設定寬版頁面，讓左右有足夠空間排版
st.set_page_config(layout="wide", page_title="文件自動蓋章工具 v3.0 (效能優化版)")

# 強制將圖片互動區塊與 Canvas 的滑鼠游標改成十字線
st.markdown(
    """
    <style>
    /* 針對 Streamlit 圖片與互動元件修改游標 */
    [data-testid="stImage"] img, canvas, .stImage {
        cursor: crosshair !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 初始化 Session State 來穩定儲存座標，避免在調整滑桿時印章消失
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
# 分兩欄上傳，保持排版整齊
col_up1, col_up2 = st.columns(2)
with col_up1:
    doc_file = st.file_uploader("上傳文件檔案 (圖片格式)", type=['png', 'jpg', 'jpeg'])
with col_up2:
    stamp_file = st.file_uploader("上傳印章檔案", type=['png', 'jpg', 'jpeg'])

# ==========================================
# 3. 主程式邏輯 (整合單一畫面 + 效能優化)
# ==========================================
if doc_file and stamp_file:
    # --- 圖片前處理：讀取並統一轉為 RGBA 支援透明度 ---
    doc_img = Image.open(doc_file).convert("RGBA")
    stamp_img = Image.open(stamp_file).convert("RGBA")

    # ==========================================
    # **效能核心優化 1：自動壓縮超大文件**
    # 如果文件原圖太大(例如 A4 原圖常常 2000px+)，先進行一次性縮放。
    # 這能解決「點點沒反應/LAG」的問題，並大大減少網路傳輸延遲。
    # ==========================================
    # 這裡的 DPI 換算僅用於保持 cm 输入有意義。
    # 假設螢幕 DPI ~96 (96 px/inch, 2.54 cm/inch)，1cm ~ 38 像素。
    # 這裡設定 1cm = 30px 作為效能與實體尺寸的保守換算值。
    pixel_per_cm = 30
    
    # 計算顯示寬度控制：預設寬度縮小 80%，意味著顯示寬度為原來的 20%。
    # 我們這裡採用的策略是限制文件的最大像素寬度，來達到效能優化。
    max_interactive_width = 1200 # 限制一個合理的像素寬度
    if doc_img.width > max_interactive_width:
        ratio = max_interactive_width / doc_img.width
        new_h = int(doc_img.height * ratio)
        # Pillow 的高效能、高質量縮放，LANCZOS 是最好的，但耗時一點。
        # 如果追求極致速度，可以用 NEAREST，但質量差。
        doc_img = doc_img.resize((max_interactive_width, new_h), Image.Resampling.LANCZOS)
        # 注意：雖然 Pillow 處理慢，但比起網路傳遞超大圖，事前壓縮是絕對能消除延遲的。

    # ==========================================
    # **預覽圖大小縮小 80%**
    # 我們在顯示預覽圖的 `streamlit_image_coordinates` 元件上控制顯示寬度。
    # **不要使用 `use_column_width=True` (滿版)**，而是將它放在一個寬度合適的欄位中。
    # ==========================================

    # --- 印章前處理 (大小、旋轉、透明度) ---
    # 根據 DPI 換算 cm 到像素，並應用旋轉和透明度。
    # 此部分保持穩定。
    target_width_px = int(stamp_width_cm * pixel_per_cm)
    stamp_ratio = target_width_px / stamp_img.width  
    new_size = (target_width_px, int(stamp_img.height * stamp_ratio))
    
    if new_size[0] > 0 and new_size[1] > 0:
        stamp_img = stamp_img.resize(new_size, Image.Resampling.LANCZOS)
    
    # 處理旋轉 (expand=True 確保旋轉後圖片不被裁切)
    stamp_img = stamp_img.rotate(rotation, expand=True)
    
    # 處理透明度 (更乾淨的寫法)
    if opacity < 1.0:
        # 單獨處理 A 通道
        alpha = stamp_img.getchannel('A')
        alpha = alpha.point(lambda p: p * opacity)
        stamp_img.putalpha(alpha)

    # ==========================================
    # **單一畫面整合版**
    # ==========================================
    st.markdown("### 👁️ 文件預覽與蓋章區")
    st.markdown("💡 **操作方式：** 直接在下方文件點擊您想蓋章的位置（游標為十字線）。如需修改，直接點擊**新的位置**，或調整左側數值即可。")

    # 複製一份文檔圖，準備顯示合成後的圖片
    display_img = doc_img.copy()

    # 如果已經有座標紀錄，就把印章合成上去
    if st.session_state.stamp_pos is not None:
        x, y = st.session_state.stamp_pos
        # 將印章貼到原圖上 (第三個參數是遮罩，確保透明度)
        display_img.paste(stamp_img, (x, y), stamp_img)

    # ==========================================
    # **版面控制：預覽圖縮小 80% (視覺上)**
    # 我們不讓圖片滿版顯示，而是使用欄位切分。
    # 例如：使用 st.columns([1, 10, 1]) 將圖片放在中欄，並關閉 use_column_width=True。
    # ==========================================
    st.markdown("<br>", unsafe_allow_html=True) # 增加一點空白排版
    pre_col1, pre_col2, pre_col3 = st.columns([1, 10, 1]) # 使用 columns 控制顯示寬度

    with pre_col2:
        # 顯示這張「可能已經蓋好章」的圖片，並持續監聽點擊
        # 重要：關閉 use_column_width=True，讓圖片按照事前壓縮後的像素大小顯示。
        clicked_value = streamlit_image_coordinates(display_img, key="interactive_canvas", use_column_width=False)

    # 如果偵測到點擊，且座標改變了，就更新狀態並強制畫面重整
    if clicked_value is not None:
        new_pos = (clicked_value["x"], clicked_value["y"])
        # 如果點擊位置變了
        if st.session_state.stamp_pos != new_pos:
            st.session_state.stamp_pos = new_pos
            # 關鍵 2：使用 st.rerun() 瞬間重新整理，讓印章馬上出現在新位置，消除拖曳感。
            st.rerun() 

else:
    st.info("請先在上方上傳「文件」與「印章」檔案。")
