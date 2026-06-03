import fitz
import sys
import os
import cv2
import numpy as np

# 复用 cv_slice 的核心逻辑
def find_split_pos_3col(mid_area, start_offset):
    w = len(mid_area)
    mid = w // 2
    left_part = mid_area[:mid]
    right_part = mid_area[mid:]
    min_idx_1 = np.argmin(left_part)
    min_idx_2 = np.argmin(right_part) + mid
    return start_offset + min_idx_1, start_offset + min_idx_2

def draw_debug_lines(input_path):
    if not os.path.exists(input_path):
        return

    doc = fitz.open(input_path)
    print(f"🕵️‍♀️ 调试模式: 正在绘制切割线 - {input_path}")

    for i in range(len(doc)):
        page = doc[i]
        # 仅横版
        if page.rect.width / page.rect.height < 1.1:
            continue

        # 1. CV 分析
        pix = page.get_pixmap(dpi=72)
        img_data = np.frombuffer(pix.samples, dtype=np.uint8)
        if pix.n >= 3:
            img = img_data.reshape(pix.height, pix.width, pix.n)
            gray = cv2.cvtColor(img[:,:,:3], cv2.COLOR_RGB2GRAY)
        else:
            gray = img_data.reshape(pix.height, pix.width)

        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        col_sum = np.sum(binary, axis=0)
        h, w = gray.shape
        
        search_start = int(w * 0.15)
        search_end = int(w * 0.85)
        mid_area = col_sum[search_start:search_end]
        
        x1, x2 = find_split_pos_3col(mid_area, search_start)
        
        # 映射回 PDF 坐标
        scale = page.rect.width / w
        pdf_x1 = x1 * scale
        pdf_x2 = x2 * scale
        
        # 2. 画线 (红色粗线)
        shape = page.new_shape()
        shape.draw_line((pdf_x1, 0), (pdf_x1, page.rect.height))
        shape.draw_line((pdf_x2, 0), (pdf_x2, page.rect.height))
        shape.finish(color=(1, 0, 0), width=2)
        shape.commit()
        
        print(f"  Page {i+1}: Lines at x={pdf_x1:.1f}, {pdf_x2:.1f}")

    output_path = input_path.replace(".pdf", "_DEBUG.pdf")
    doc.save(output_path)
    print(f"✅ 调试文件生成: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_cv.py <pdf>")
    else:
        draw_debug_lines(sys.argv[1])
