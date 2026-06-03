import fitz
import sys
import os
import cv2
import numpy as np

def find_split_pos(page):
    """
    使用 OpenCV 智能识别页面中间的白色缝隙
    返回: 相对位置 (0.0 - 1.0)，例如 0.51 表示在 51% 处切割
    """
    # 1. 获取页面快照 (转为图片)
    pix = page.get_pixmap(dpi=72)
    img_data = np.frombuffer(pix.samples, dtype=np.uint8)
    
    # 格式转换: PyMuPDF 出来的通常是 RGB
    if pix.n == 3:
        img = img_data.reshape(pix.height, pix.width, 3)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    elif pix.n == 4:
        img = img_data.reshape(pix.height, pix.width, 4)
        gray = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
    else:
        img = img_data.reshape(pix.height, pix.width)
        gray = img # 已经是灰度

    # 2. 反转图像 (字变亮，背景变黑)，便于统计
    # 注意：扫描件可能有噪点，先做简单的阈值处理
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # 3. 垂直投影 (统计每一列的白色像素点数量)
    # 结果是一个数组，长度等于图片宽度，值越高代表这一列字越多
    col_sum = np.sum(binary, axis=0)
    
    # 4. 在中间区域搜索最佳分割点
    # 假设中缝一定在 35% ~ 65% 之间
    h, w = gray.shape
    search_start = int(w * 0.35)
    search_end = int(w * 0.65)
    
    mid_area = col_sum[search_start:search_end]
    
    # 使用卷积平滑一下曲线，避免因为个别噪点导致切歪
    # window_size = 10
    # kernel = np.ones(window_size) / window_size
    # smoothed = np.convolve(mid_area, kernel, mode='same')

    # 5. 找最小值 (字最少的地方就是缝隙)
    min_idx = np.argmin(mid_area)
    
    # 还原为绝对坐标
    best_x = search_start + min_idx
    
    # 相对坐标
    ratio = best_x / w
    
    print(f"    👀 视觉分析: 最佳分割点在 {ratio:.2%} 处 (像素x={best_x})")
    
    return ratio

def find_split_pos_3col(mid_area, start_offset):
    """
    专门针对三栏寻找两个切割点
    """
    # 简单策略：将中间区域再分为左右两半，分别找最小值
    w = len(mid_area)
    mid = w // 2
    
    left_part = mid_area[:mid]
    right_part = mid_area[mid:]
    
    min_idx_1 = np.argmin(left_part)
    min_idx_2 = np.argmin(right_part) + mid
    
    # 还原为绝对坐标
    x1 = start_offset + min_idx_1
    x2 = start_offset + min_idx_2
    
    return x1, x2

def detect_3_columns(page):
    """
    返回三个 fitz.Rect 对象 [col1, col2, col3]
    """
    # 1. 图像分析
    pix = page.get_pixmap(dpi=72)
    img_data = np.frombuffer(pix.samples, dtype=np.uint8)
    if pix.n >= 3:
        # 正确处理多通道
        c = pix.n
        img = img_data.reshape(pix.height, pix.width, c)
        # 只要前3个通道(RGB)转灰度，忽略Alpha
        gray = cv2.cvtColor(img[:,:,:3], cv2.COLOR_RGB2GRAY)
    else:
        gray = img_data.reshape(pix.height, pix.width)

    # 简单二值化
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    col_sum = np.sum(binary, axis=0)
    
    h, w = gray.shape
    
    # 搜索范围：整个中间区域 (15% - 85%) 
    # 三栏分界线通常在 1/3 (33%) 和 2/3 (66%) 附近
    search_start = int(w * 0.15)
    search_end = int(w * 0.85)
    
    mid_area = col_sum[search_start:search_end]
    
    # 找两个点
    x1, x2 = find_split_pos_3col(mid_area, search_start)
    
    print(f"    👀 三栏识别: 切割线位于 {x1} ({x1/w:.2%}), {x2} ({x2/w:.2%})")
    
    # 构建 Rect (注意还要转回 PDF 的坐标系)
    # pix.width 和 page.rect.width 可能不一样 (DPI不同)
    scale = page.rect.width / w
    
    rx1 = x1 * scale
    rx2 = x2 * scale
    pw = page.rect.width
    ph = page.rect.height
    
    r1 = fitz.Rect(0, 0, rx1, ph)
    r2 = fitz.Rect(rx1, 0, rx2, ph)
    r3 = fitz.Rect(rx2, 0, pw, ph)
    
    return [r1, r2, r3]

def slice_pdf_cv(input_path, skip_first_n=0, mode="2_col"):
    if not os.path.exists(input_path):
        print(f"❌ 错误: 文件 {input_path} 不存在")
        return

    doc_src = fitz.open(input_path)
    doc_new = fitz.open() # 最终文档

    print(f"🚀 开始智能视觉切割: {input_path}")
    print(f"🧠 模式: {mode}")
    
    # 队列：存放所有切割下来的长条 (PageObject, Rect)
    column_queue = []

    # 1. 遍历并提取所有列
    processed_pages = 0
    for i in range(len(doc_src)):
        page = doc_src[i]
        
        # 宽 > 高 且 宽/高 > 1.2 才切 (横版A3)
        if page.rect.width / page.rect.height > 1.2:
            processed_pages += 1
            print(f"  📖 分析第 {i+1} 页...")
            
            try:
                if mode == "3to2": # 三栏转两栏
                    cols = detect_3_columns(page) # 返回 [r1, r2, r3]
                    for r in cols:
                        column_queue.append( (i, r) )
                else: 
                    # 默认两栏逻辑 (旧逻辑)
                    split_ratio = find_split_pos(page)
                    w = page.rect.width
                    h = page.rect.height
                    x = w * split_ratio
                    column_queue.append( (i, fitz.Rect(0, 0, x, h)) )
                    column_queue.append( (i, fitz.Rect(x, 0, w, h)) )
            except Exception as e:
                print(f"    ⚠️ 视觉分析出错: {e}")
                # Fallback: 均分
                w = page.rect.width
                h = page.rect.height
                if mode == "3to2":
                    d = w/3
                    column_queue.append( (i, fitz.Rect(0,0,d,h)) )
                    column_queue.append( (i, fitz.Rect(d,0,d*2,h)) )
                    column_queue.append( (i, fitz.Rect(d*2,0,w,h)) )
                else:
                    column_queue.append( (i, fitz.Rect(0,0,w/2,h)) )
                    column_queue.append( (i, fitz.Rect(w/2,0,w,h)) )
        else:
            # 竖版页面，如何处理？
            # 放入队列作为一个“全宽”的元素？
            # 简单起见：如果是竖版，直接作为一个单独的 A4 页插入到 doc_new
            # 先把队列里的清空到 PDF 
            pass 
            # 暂时策略：竖版页放到“特殊队列”或者直接最后处理
            # 也就是先把前面的 Columns 拼完，再插入这个竖页
            # 为了简化逻辑，我们在拼版循环里遇到特殊标记再处理
            column_queue.append( (i, "FULL_PAGE") )

    # 2. 只有提取完所有列，才能开始“跨页拼接” (Reflow)
    # 如果 mode == "3to2"，我们要把队列里的列，每两个拼成一个 A4
    if mode == "3to2":
        print(f"🧩 开始拼接 (共 {len(column_queue)} 个分栏)...")
        
        # A4 尺寸 (Portrait)
        A4_W, A4_H = 595, 842
        
        # 我们一次取 2 个栏
        chunk_size = 2
        for k in range(0, len(column_queue), chunk_size):
            chunk = column_queue[k : k+chunk_size]
            
            # 创建新 A4 页
            new_page = doc_new.new_page(width=A4_W, height=A4_H)
            
            # 布局参数
            # 我们有两个只有 1/3 A3 宽度的条，要放到 A4 上
            # 源宽度 approx 400pt, A4宽度 595pt. 
            # 两个放进去 800pt > 595pt. 需要缩放
            
            # 布局优化: 参考 HTML 逻辑，增加间距 (Gutter)
            # A4 尺寸: 595 x 842
            GUTTER = 20 # 间隔 (pt)
            MARGIN = 10 # 左右边距
            
            # 可用宽度
            avail_w = A4_W - (MARGIN * 2) - ((chunk_size - 1) * GUTTER)
            col_target_w = avail_w / chunk_size
            
            for idx, (pg_num, rect) in enumerate(chunk):
                if rect == "FULL_PAGE":
                    # 竖版直接插入（逻辑不变）
                    src_page = doc_src[pg_num]
                    p = doc_new.new_page(width=src_page.rect.width, height=src_page.rect.height)
                    p.show_pdf_page(p.rect, doc_src, pg_num, rotate=src_page.rotation)
                    continue

                # 计算缩放
                src_w = rect.width
                src_h = rect.height
                
                scale = col_target_w / src_w
                # 高度限制 (留出上下一点边距)
                if src_h * scale > (A4_H - 40):
                    scale = (A4_H - 40) / src_h
                
                dest_w = src_w * scale
                dest_h = src_h * scale
                
                # 计算位置
                # X: 左边距 + (列宽+间距)*index + (列宽-实际宽)/2 [居中]
                # 简化：直接左对齐或居中
                
                base_x = MARGIN + idx * (col_target_w + GUTTER)
                # 在自己的槽位内居中
                offset_x = (col_target_w - dest_w) / 2
                final_x = base_x + offset_x
                
                # Y: 垂直居中
                final_y = (A4_H - dest_h) / 2
                
                dest_rect = fitz.Rect(final_x, final_y, final_x + dest_w, final_y + dest_h)
                
                # 绘制
                new_page.show_pdf_page(dest_rect, doc_src, pg_num, clip=rect, rotate=doc_src[pg_num].rotation)

    else:
        # 旧逻辑：Queue 模式的普通输出
        if mode != "3to2":
             for (pg_num, rect) in column_queue:
                src_page = doc_src[pg_num]
                if rect == "FULL_PAGE":
                    p = doc_new.new_page(width=src_page.rect.width, height=src_page.rect.height)
                    p.show_pdf_page(p.rect, doc_src, pg_num, rotate=src_page.rotation)
                else:
                    p = doc_new.new_page(width=rect.width, height=rect.height)
                    p.show_pdf_page(p.rect, doc_src, pg_num, clip=rect, rotate=src_page.rotation)

    # 3. 后处理：跳过前 N 页
    if skip_first_n > 0:
        if len(doc_new) > skip_first_n:
            doc_new.delete_pages(range(skip_first_n))
            print(f"✂️  已删除前 {skip_first_n} 页")


    # 保存
    dir_name = os.path.dirname(input_path)
    base_name = os.path.basename(input_path)
    name_root, ext = os.path.splitext(base_name)
    output_filename = f"{name_root}_智能版{ext}"
    output_path = os.path.join(dir_name, output_filename)

    doc_new.save(output_path)
    doc_src.close()
    doc_new.close()
    
    print("-" * 30)
    print(f"🎉 全部完成！输出文件: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python cv_slice.py <pdf文件> [skip_n] [mode]")
        print("示例: python cv_slice.py a3.pdf 0 3to2")
    else:
        f_path = sys.argv[1]
        skip = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        mode = sys.argv[3] if len(sys.argv) > 3 else "2_col"
        slice_pdf_cv(f_path, skip, mode)
