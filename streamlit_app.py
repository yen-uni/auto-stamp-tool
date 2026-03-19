import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io
from streamlit_cropper import st_cropper

st.set_page_config(page_title="環久國際機構-蓋章小工具V8 (視覺對位版)", page_icon="📄", layout="wide")

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

st.title("📄 環久國際機構-蓋章小工具V8 (視覺校正版)")

# ==========================================
# 側邊欄：全域印章設定 (步驟一與步驟二共用)
# ==========================================
st.sidebar.header("⚙️ 印章參數設定 (全域)")
st.sidebar.info("請在「步驟一」視覺對照時調整此處數值，確認大小無誤後再進行「步驟二」。")
stamp_w_cm = st.sidebar.number_input("📐 印章寬度 (公分)", value=3.00, min_value=0.10, max_value=20.00, step=0.10, format="%.2f")
stamp_opacity = st.sidebar.slider("💧 印章不透明度", 0.1, 1.0, 0.75, 0.05, help="對照時建議調低透明度，套印時可調回 1.0")
auto_bg_remove = st.sidebar.checkbox("✨ 自動濾除印章白底", value=True)
rotation_angle = st.sidebar.select_slider("🔄 印章旋轉角度", options=[0, 90, 180, 270, 360], value=0)

# ==========================================
# 主畫面：雙步驟流程
# ==========================================
tab1, tab2 = st.tabs(["📍 步驟一：視覺對照確認尺寸", "🖨️ 步驟二：套印新文件"])

# ------------------------------------------
# 📍 步驟一：視覺對照確認尺寸
# ------------------------------------------
with tab1:
    st.markdown("### 1. 上傳檔案與印章")
    col_upload1, col_upload2 = st.columns(2)
    with col_upload1:
        ref_pdf_file = st.file_uploader("📁 上傳「已蓋章」參考 PDF (對照用)", type=["pdf"], key="ref_pdf")
    with col_upload2:
        stamp_file = st.file_uploader("💮 上傳印章圖檔", type=["png", "jpg", "jpeg"], key="stamp")

    if ref_pdf_file and stamp_file:
        st.markdown("---")
        st.markdown("### 2. 拖曳對照尺寸")
        st.info("💡 **操作方式**：將紅框拖曳到參考文件上的舊印章位置，並調整左側的「印章寬度(公分)」，直到下方預覽圖的數位印章與舊印章大小完美重合。")
        
        # 讀取參考 PDF 第一頁作為底圖
        ref_doc = fitz.open(stream=ref_pdf_file.read(), filetype="pdf")
        ref_page = ref_doc[0]
        ref_pix = ref_page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
        ref_bg_img = Image.frombytes("RGB", [ref_pix.width, ref_pix.height], ref_pix.samples)
        
        # 處理數位印章
        stamp_file.seek(0)
        final_stamp = process_stamp(stamp_file, auto_bg_remove, False, False, rotation_angle, stamp_opacity)
        
        col_ref1, col_ref2 = st.columns([1.2, 1])
        with col_ref1:
            # 取得對準座標
            ref_coords = st_cropper(ref_bg_img, aspect_ratio=None, box_color='#0000FF', return_type='box', key='ref_cropper')
        
        with col_ref2:
            st.markdown("**🔍 對照預覽區**")
            # 換算尺寸與紅框中心點
            stamp_w_pts = stamp_w_cm * CM_TO_PTS
            pillow_ratio = final_stamp.width / final_stamp.height
            stamp_h_pts = stamp_w_pts / pillow_ratio
            
            center_x = ref_coords['left'] + (ref_coords['width'] / 2)
            center_y = ref_coords['top'] + (ref_coords['height'] / 2)
            
            # 從中心點反推左上/右下座標
            rect_x0 = center_x - (stamp_w_pts / 2)
            rect_y0 = center_y - (stamp_h_pts / 2)
            rect_x1 = center_x + (stamp_w_pts / 2)
            rect_y1 = center_y + (stamp_h_pts / 2)
            
            # 將數位印章貼上預覽圖
            preview_doc = fitz.open(stream=ref_pdf_file.getvalue(), filetype="pdf")
            rect = fitz.Rect(rect_x0, rect_y0, rect_x1, rect_y1)
            
            stamp_bytes_io = io.BytesIO()
            final_stamp.save(stamp_bytes_io, format="PNG")
            preview_doc[0].insert_image(rect, stream=stamp_bytes_io.getvalue())
            
            # 渲染高畫質預覽
            zoom_matrix = fitz.Matrix(2.0, 2.0)
            preview_img_pix = preview_doc[0].get_pixmap(matrix=zoom_matrix)
            preview_img = Image.frombytes("RGB", [preview_img_pix.width, preview_img_pix.height], preview_img_pix.samples)
            
            st.image(preview_img, caption=f"對位預覽 (印章設定為 {stamp_w_cm} 公分)", use_container_width=True)
            st.success("✅ 尺寸確認 OK 後，請切換到上方「步驟二」頁籤。")

# ------------------------------------------
# 🖨️ 步驟二：套印新文件
# ------------------------------------------
with tab2:
    st.markdown("### 1. 上傳空白文件")
    target_pdf_file = st.file_uploader("📁 上傳欲套印之「空白」 PDF 檔案", type=["pdf"], key="target_pdf")
    
    if target_pdf_file and stamp_file:
        st.markdown("---")
        st.markdown("### 2. 中心點定位與蓋章")
        st.info("💡 **提示**：請移動紅框，將紅框的 **「正中心」** 對準您要蓋章的目標位置。系統會以紅框中心點作為印章的正中心進行套印。")
        
        target_doc = fitz.open(stream=target_pdf_file.read(), filetype="pdf")
        
        c_mode, c_page = st.columns(2)
        with c_mode:
            apply_mode = st.radio("蓋章範圍", ["單頁", "全頁 (所有頁面)"], horizontal=True)
        with c_page:
            page_num = st.number_input("目標頁數", min_value=1, max_value=len(target_doc), value=1)
            page_index = page_num - 1
            
        target_page = target_doc[page_index]
        target_pix = target_page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
        target_bg_img = Image.frombytes("RGB", [target_pix.width, target_pix.height], target_pix.samples)
        
        col_main1, col_main2 = st.columns([1.2, 1])
        
        with col_main1:
            # 取得紅框座標
            box_coords = st_cropper(target_bg_img, aspect_ratio=None, box_color='#FF0000', return_type='box', key='target_cropper')
            
        with col_main2:
            st.markdown("**📄 最終成品預覽**")
            
            # 重新處理一次印章 (以防使用者在側邊欄改了設定)
            stamp_file.seek(0)
            final_stamp = process_stamp(stamp_file, auto_bg_remove, False, False, rotation_angle, stamp_opacity)
            stamp_bytes_io = io.BytesIO()
            final_stamp.save(stamp_bytes_io, format="PNG")
            
            # --- 核心邏輯：紅框正中心換算 ---
            center_x = box_coords['left'] + (box_coords['width'] / 2)
            center_y = box_coords['top'] + (box_coords['height'] / 2)
            
            stamp_w_pts = stamp_w_cm * CM_TO_PTS
            pillow_ratio = final_stamp.width / final_stamp.height
            stamp_h_pts = stamp_w_pts / pillow_ratio
            
            rect_x0 = center_x - (stamp_w_pts / 2)
            rect_y0 = center_y - (stamp_h_pts / 2)
            rect_x1 = center_x + (stamp_w_pts / 2)
            rect_y1 = center_y + (stamp_h_pts / 2)
            
            rect = fitz.Rect(rect_x0, rect_y0, rect_x1, rect_y1)
            
            # 執行蓋章
            if apply_mode == "全頁 (所有頁面)":
                for p in target_doc:
                    p.insert_image(rect, stream=stamp_bytes_io.getvalue())
            else:
                target_page.insert_image(rect, stream=stamp_bytes_io.getvalue())
                
            # 渲染高畫質成品預覽
            zoom_matrix = fitz.Matrix(2.0, 2.0)
            final_pix = target_page.get_pixmap(matrix=zoom_matrix)
            final_img = Image.frombytes("RGB", [final_pix.width, final_pix.height], final_pix.samples)
            
            st.image(final_img, caption="最終成品預覽 (中心點對位)", use_container_width=True)
            
            output_pdf = io.BytesIO()
            target_doc.save(output_pdf)
            
            st.download_button(
                label="📥 點我下載已蓋章 PDF",
                data=output_pdf.getvalue(),
                file_name=f"套印完成_{target_pdf_file.name}",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
