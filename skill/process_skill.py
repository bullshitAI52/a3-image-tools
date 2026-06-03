import os
import sys
import glob
import fitz # PyMuPDF

# Ensure we can find the backend script
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, "skill_backend"))

try:
    from cli_slice import slice_pdf
except ImportError:
    print("❌ Error: Could not import skill_backend/cli_slice.py")
    sys.exit(1)

import fitz

def convert_image_to_pdf(image_path, output_pdf_path):
    """
    Convert an image to a single-page PDF.
    """
    try:
        doc = fitz.open()
        img = fitz.open(image_path)
        rect = img[0].rect
        pdfbytes = img.convert_to_pdf()
        img.close()
        
        img_pdf = fitz.open("pdf", pdfbytes)
        page = doc.new_page(width=rect.width, height=rect.height)
        page.show_pdf_page(page.rect, img_pdf, 0)
        
        doc.save(output_pdf_path)
        doc.close()
        return True
    except Exception as e:
        print(f"❌ Failed to convert image {os.path.basename(image_path)}: {e}")
        return False

def main():
    input_dir = os.path.join(current_dir, "input")
    output_dir = os.path.join(current_dir, "output")
    temp_dir = os.path.join(current_dir, "temp_pdf_conversion")

    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
        print(f"Created input directory: {input_dir}")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # Gather all files
    all_files = glob.glob(os.path.join(input_dir, "*"))
    
    # Filter for supported types
    pdf_files = [f for f in all_files if f.lower().endswith('.pdf')]
    image_files = [f for f in all_files if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    if not pdf_files and not image_files:
        print(f"⚠️  No recognizable files (PDF/JPG/PNG) found in {input_dir}")
        return

    print(f"🔍 Found {len(pdf_files)} PDF files and {len(image_files)} Image files.")

    # 1. Process PDFs directly
    for pdf_path in pdf_files:
        print(f"\nProcessing PDF: {os.path.basename(pdf_path)}")
        try:
            slice_pdf(pdf_path, mode='2_col', skip_first_n=0, output_dir=output_dir)
        except Exception as e:
            print(f"❌ Failed to process {os.path.basename(pdf_path)}: {e}")

    # 2. Process Images (Convert -> Slice -> Clean)
    if image_files:
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            
        for img_path in image_files:
            print(f"\nProcessing Image: {os.path.basename(img_path)}")
            
            # Temporary PDF path
            base_name = os.path.basename(img_path)
            name_root, _ = os.path.splitext(base_name)
            temp_pdf_path = os.path.join(temp_dir, f"{name_root}.pdf")
            
            # Convert
            if convert_image_to_pdf(img_path, temp_pdf_path):
                print(f"  ✅ Converted to PDF: {temp_pdf_path}")
                # Process
                try:
                    slice_pdf(temp_pdf_path, mode='2_col', skip_first_n=0, output_dir=output_dir)
                except Exception as e:
                    print(f"❌ Failed to process slice logic for {base_name}: {e}")
                
                # Cleanup single temp file (optional, or keep for debugging)
                # os.remove(temp_pdf_path)
            
        print(f"\nℹ️  Temporary PDFs are in: {temp_dir}")

    print("\n✅ Batch processing complete!")

if __name__ == "__main__":
    main()
