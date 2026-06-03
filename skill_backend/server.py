import fitz  # PyMuPDF
import os
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import uvicorn
import shutil

# ==========================================
# 这是一个模拟 "AI Skill" 的后端服务
# 使用 FastAPI 构建，支持被 Coze/Dify 调用
# ==========================================

app = FastAPI(title="Exam Slicer Skill", description="自动将 A3 试卷切割为 A4")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
PROCESSED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "processed")

# 确保目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

def split_page(doc_out, src_page, mode='2_col'):
    """
    核心切割逻辑：使用 PDF 裁剪框 (CropBox) 实现无损切割
    """
    rect = src_page.rect
    width = rect.width
    height = rect.height
    
    # 简单的分栏策略
    sub_rects = []
    
    if mode == '2_col':
        # 左右两栏 (适合普通 A3 试卷)
        # 左半边
        r1 = fitz.Rect(0, 0, width / 2, height)
        # 右半边
        r2 = fitz.Rect(width / 2, 0, width, height)
        sub_rects = [r1, r2]
        
    elif mode == '3_col':
        # 三栏 (适合语文/英语长试卷)
        one_third = width / 3
        r1 = fitz.Rect(0, 0, one_third, height)
        r2 = fitz.Rect(one_third, 0, one_third * 2, height)
        r3 = fitz.Rect(one_third * 2, 0, width, height)
        sub_rects = [r1, r2, r3]
        
    else:
        # 不切，直接原样放
        sub_rects = [rect]

    # 将切好的区域放入新文档
    for r in sub_rects:
        # 在输出文档创建新页面 (大小等于切割区域)
        # 如果需要强制转 A4，可以在这里缩放，但简单的做法是保持切割后的尺寸
        new_page = doc_out.new_page(width=r.width, height=r.height)
        
        # 将原页面的内容绘制到新页面对应的位置
        # 这里的技巧是：在新页面上显示原页面的一个"窗口"
        new_page.show_pdf_page(
            new_page.rect,   # 新页面的填满区域
            doc_out,         # 引用同一个文档（稍后合并）或者原文档
            src_page.number, # 原页码
            clip=r           # 只显示这个区域
        )

@app.post("/slice_pdf")
async def slice_pdf_endpoint(file: UploadFile = File(...), mode: str = "2_col"):
    """
    API 接口：接收 PDF，返回切割后的 PDF
    mode: '2_col' (两栏) 或 '3_col' (三栏)
    """
    # 1. 保存上传的文件
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. 处理 PDF
    output_filename = f"sliced_{file.filename}"
    output_path = os.path.join(PROCESSED_DIR, output_filename)
    
    try:
        doc_src = fitz.open(input_path)
        doc_out = fitz.open() # 空的新 PDF
        
        # 将原文档作为底层资源引入，避免字体丢失
        # 这里的逻辑稍作调整：PyMuPDF 的 show_pdf_page 需要源文档对象
        
        for i in range(len(doc_src)):
            page = doc_src[i]
            # 只有横向页面才切割 (宽 > 高)
            if page.rect.width > page.rect.height:
                # 执行切割逻辑 (注意：show_pdf_page 需要 doc_src)
                # 因为 doc_out 和 doc_src 是不同对象，show_pdf_page 支持跨文档复制
                
                rect = page.rect
                w = rect.width
                h = rect.height
                
                rects = []
                if mode == '2_col':
                    rects = [
                        fitz.Rect(0, 0, w/2, h),
                        fitz.Rect(w/2, 0, w, h)
                    ]
                elif mode == '3_col':
                    d = w/3
                    rects = [
                        fitz.Rect(0, 0, d, h),
                        fitz.Rect(d, 0, d*2, h),
                        fitz.Rect(d*2, 0, w, h)
                    ]
                
                for r in rects:
                    new_page = doc_out.new_page(width=r.width, height=r.height)
                    new_page.show_pdf_page(new_page.rect, doc_src, i, clip=r)
                    
            else:
                # 已经是竖向的，直接复制整页
                new_page = doc_out.new_page(width=page.rect.width, height=page.rect.height)
                new_page.show_pdf_page(new_page.rect, doc_src, i)
        
        doc_out.save(output_path)
        doc_src.close()
        doc_out.close()
        
        # 3. 返回文件
        return FileResponse(output_path, media_type='application/pdf', filename=output_filename)
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print("启动 Skill 服务: http://127.0.0.1:8000")
    print("API 文档: http://127.0.0.1:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
