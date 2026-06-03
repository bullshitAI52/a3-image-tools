import fitz
import sys
import os

def slice_pdf(input_path, mode='2_col', skip_first_n=0, output_dir=None):
    if not os.path.exists(input_path):
        print(f"❌ 错误: 文件 {input_path} 不存在")
        return

    try:
        doc_src = fitz.open(input_path)
    except Exception as e:
        print(f"❌ 无法打开 PDF 文件: {e}")
        return

    doc_out = fitz.open()

    print(f"🚀 开始处理: {input_path}")
    print(f"⚙️  模式: {'三栏切割' if mode == '3_col' else '两栏切割 (A3转A4)'}")
    if skip_first_n > 0:
        print(f"✂️  将跳过前 {skip_first_n} 页 (生成后)")

    processed_count = 0
    
    # 临时文档，用于先存放所有页面
    doc_temp = fitz.open()

    for i in range(len(doc_src)):
        page = doc_src[i]
        
        # 智能判断：只有横向页面（宽 > 高 且 宽高比明显）才切
        # 宽/高 > 1.2 认为确实是横版
        if page.rect.width / page.rect.height > 1.2:
            rect = page.rect
            w = rect.width
            h = rect.height
            
            rects = []
            if mode == '2_col': # 左右切
                rects = [
                    fitz.Rect(0, 0, w/2, h),
                    fitz.Rect(w/2, 0, w, h)
                ]
            elif mode == '3_col': # 三栏切
                d = w/3
                rects = [
                    fitz.Rect(0, 0, d, h),
                    fitz.Rect(d, 0, d*2, h),
                    fitz.Rect(d*2, 0, w, h)
                ]
            
            for r in rects:
                # new_page = doc_out.new_page(width=r.width, height=r.height)
                # 优化：通常我们想转成标准 A4 尺寸 (595x842)，或者保持比例
                # 这里我们保持切割后的原始尺寸，这样最安全
                new_page = doc_temp.new_page(width=r.width, height=r.height)
                
                # 核心魔法：无损矢量复制
                new_page.show_pdf_page(new_page.rect, doc_src, i, clip=r)
            
            processed_count += 1
            print(f"  ✅ 第 {i+1} 页: 已切割 ({len(rects)} 份)")

        else:
            # 竖向页面直接复制
            new_page = doc_temp.new_page(width=page.rect.width, height=page.rect.height)
            new_page.show_pdf_page(new_page.rect, doc_src, i)
            print(f"  👉 第 {i+1} 页: 保持原样 (竖版)")

    # --- 最终处理：跳过前 N 页 ---
    if skip_first_n > 0:
        if len(doc_temp) > skip_first_n:
            # 这种做法最高效：删除前 N 页
            doc_temp.delete_pages(range(skip_first_n))
            print(f"🗑️  已删除前 {skip_first_n} 页，剩余 {len(doc_temp)} 页")
        else:
            print(f"⚠️  警告: 总页数 ({len(doc_temp)}) 少于要跳过的页数 ({skip_first_n})，未删除任何页面")

    # 生成输出文件名
    dir_name = output_dir if output_dir else os.path.dirname(input_path)
    base_name = os.path.basename(input_path)
    name_root, ext = os.path.splitext(base_name)
    output_filename = f"{name_root}_切分版_去头{skip_first_n}页{ext}" if skip_first_n > 0 else f"{name_root}_切分版{ext}"
    output_path = os.path.join(dir_name, output_filename)

    doc_temp.save(output_path)
    doc_src.close()
    doc_temp.close()
    
    print("-" * 30)
    print(f"🎉 全部完成！")
    print(f"📄 共处理横版页面: {processed_count} 页")
    print(f"💾 输出文件: {output_path}")

# 使用方法: python cli_slice.py 文件名.pdf [2_col 或 3_col] [skip_n]
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\n🛠️  A3试卷切割工具 (命令行版) 🛠️")
        print("用法: python cli_slice.py <pdf文件> [模式] [跳过前N页]")
        print("\n参数:")
        print("  <pdf文件>:      支持绝对路径或相对路径")
        print("  [模式]:         可选 '2_col' 或 '3_col' (默认 2_col)")
        print("  [跳过前N页]:    可选，数字，例如 5 (默认 0)")
        print("\n示例:")
        print("  python cli_slice.py math.pdf 2_col 5  (切完后删掉前5张)")
    else:
        f_path = sys.argv[1]
        m = sys.argv[2] if len(sys.argv) > 2 else '2_col'
        
        # 尝试解析第3个参数为数字
        skip = 0
        if len(sys.argv) > 3:
            try:
                skip = int(sys.argv[3])
            except:
                pass 
                
        slice_pdf(f_path, m, skip)
