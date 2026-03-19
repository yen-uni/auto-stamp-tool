import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io
from streamlit_cropper import st_cropper

st.set_page_config(page_title="環久國際機構-蓋章小工具V8.2 (多章強化版)", page_icon="📄", layout="wide")

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
    
    # 2. 自動裁切透明邊界
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
        bbox2 = img.getbbox()
        if bbox2:
            img = img.crop(bbox2)
            
    return img

st.title("📄 環久國際機構-蓋章小工具V8.2")

# ==========================================
# 側邊欄：全域印章設定
# ==========================================
st.sidebar.header("⚙️ 全域參數設定")
auto_bg_remove = st.sidebar.checkbox("✨ 自動濾除印章白底", value=True)
global_opacity = st.sidebar.slider("💧 預覽不透明度", 0.1, 1.0, 0.75, 0.05, help="對照時建議調低，正式套印建議 1.0")

# ==========================================
# 主畫面：三步驟流程
# ==========================================
tab1, tab2, tab3 = st.tabs(["📍 步驟一：尺寸對照", "🖨️ 步驟二：單印章套印", "📑 步驟三：多印章套印"])

# ------------------------------------------
# 📍 步驟一：視覺對照確認尺寸 (保持原邏輯)
# ------------------------------------------
with tab1:
    st.markdown("### 1. 尺寸參考對照")
    col_u1, col_u2 = st.columns(2)
    with col_u1: ref_pdf_file = st.file_uploader("📁 上傳參考 PDF", type=["pdf"], key="ref_pdf")
    with col_u2: stamp_file = st.file_uploader("💮 上傳印章圖檔", type=["png", "jpg"], key="stamp")

    if ref_pdf_file and stamp_file:
        stamp_w_cm_ref = st.number_input("📐 調整印章寬度 (公分)", value=3.00, step=0.10, key="w_ref")
        
        ref_doc = fitz.open(stream=ref_pdf_file.read(), filetype="pdf")
        ref_page = ref_doc[0]
        ref_pix = ref_page.get_pixmap()
        ref_bg_img = Image.frombytes("RGB", [ref_pix.width, ref_pix.height], ref_pix.samples)
        
        col_ref1, col_ref2 = st.columns([1.2, 1])
        with col_ref1:
            ref_coords = st_cropper(ref_bg_img, box_color='#0000FF', return_type='box', key='ref_cropper')
        with col_ref2:
            st.success("在此確認印章寬度數值後，請記下該數值。")
            final_stamp_ref = process_stamp(stamp_file, auto_bg_remove, False, False, 0, global_opacity)
            # ... (中間對照預覽邏輯同原版)
            st.info(f"當前設定寬度：{stamp_w_cm_ref} cm")

# ------------------------------------------
# 🖨️ 步驟二：單印章套印 (原有的快速模式)
# ------------------------------------------
with tab2:
    st.markdown("### ⚡ 快速單章套印")
    target_pdf_file = st.file_uploader("📁 上傳空白 PDF", type=["pdf"], key="target_pdf")
    if target_pdf_file and stamp_file:
        # 這裡套用原本你的單章邏輯...
        st.info("此處為原本的快速蓋章功能，僅支援單一印章。")

# ------------------------------------------
# 📑 步驟三：多印章套印 (新開發功能)
# ------------------------------------------
with tab3:
    st.markdown("### 🏗️ 多印章進階配置")
    multi_pdf = st.file_uploader("📁 上傳欲套印 PDF (多章模式)", type=["pdf"], key="multi_pdf")
    
    if multi_pdf:
        st.markdown("---")
        col_cfg1, col_cfg2 = st.columns([1, 2])
        with col_cfg1:
            stamp_count = st.number_input("🔢 需要蓋幾個不同的章？", min_value=1, max_value=6, value=3)
            page_num_multi = st.number_input("📄 目標頁碼", min_value=1, value=1)
        
        # 準備暫存資料的清單
        all_stamps_data = []
        
        # 讀取 PDF 背景圖
        doc_multi = fitz.open(stream=multi_pdf.read(), filetype="pdf")
        page_multi = doc_multi[page_num_multi-1]
        pix_multi = page_multi.get_pixmap()
        bg_multi = Image.frombytes("RGB", [pix_multi.width, pix_multi.height], pix_multi.samples)

        st.markdown("### 2. 各別印章設定")
        # 迴圈動態產生配置區
        for i in range(stamp_count):
            with st.expander(f"📌 第 {i+1} 個印章設定", expanded=(i==0)):
                c1, c2 = st.columns([1, 1.5])
                with c1:
                    s_file = st.file_uploader(f"💮 上傳印章 {i+1}", type=["png", "jpg"], key=f"s_f_{i}")
                    s_w = st.number_input(f"📐 寬度 (cm)", value=3.0, key=f"s_w_{i}")
                    s_rot = st.selectbox(f"🔄 旋轉", [0, 90, 180, 270], key=f"s_r_{i}")
                with c2:
                    if s_file:
                        st.caption("請將紅框中心對準蓋章位置")
                        coords = st_cropper(bg_multi, box_color='#FF0000', return_type='box', key=f"s_c_{i}")
                        all_stamps_data.append({
                            "file": s_file, "width": s_w, "rot": s_rot, "coords": coords
                        })
                    else:
                        st.warning("請先上傳印章圖檔")

        st.markdown("---")
        if len(all_stamps_data) == stamp_count:
            if st.button("🚀 開始一鍵合成所有印章", type="primary", use_container_width=True):
                with st.spinner("正在合成中..."):
                    # 執行所有蓋章動作
                    for data in all_stamps_data:
                        data["file"].seek(0)
                        # 處理圖檔
                        processed = process_stamp(data["file"], auto_bg_remove, False, False, data["rot"], 1.0)
                        img_byte_arr = io.BytesIO()
                        processed.save(img_byte_arr, format='PNG')
                        
                        # 計算座標
                        cx = data["coords"]['left'] + (data["coords"]['width'] / 2)
                        cy = data["coords"]['top'] + (data["coords"]['height'] / 2)
                        sw_pts = data["width"] * CM_TO_PTS
                        sh_pts = sw_pts / (processed.width / processed.height)
                        
                        rect = fitz.Rect(cx - sw_pts/2, cy - sh_pts/2, cx + sw_pts/2, cy + sh_pts/2)
                        page_multi.insert_image(rect, stream=img_byte_arr.getvalue())
                    
                    # 匯出
                    out_multi = io.BytesIO()
                    doc_multi.save(out_multi)
                    
                    st.success("✅ 全部印章套印完成！")
                    st.download_button(
                        label="📥 下載多章合成文件",
                        data=out_multi.getvalue(),
                        file_name=f"多章套印_{multi_pdf.name}",
                        mime="application/pdf",
                        use_container_width=True
                    )
