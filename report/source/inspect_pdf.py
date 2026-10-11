import pymupdf
import os

doc = pymupdf.open('report/final_case_study.pdf')
print(f"Total Pages: {len(doc)}")
for i, page in enumerate(doc):
    text = page.get_text()
    lines = [l.strip() for l in text.split('\n') if l.strip() and not l.strip().isdigit()]
    sample = " | ".join(lines[:3]) if lines else "[EMPTY]"
    imgs = page.get_images()
    print(f"Page {i+1:02d}: Images={len(imgs):2d} | Text Len={len(text):4d} | {sample[:80]}")
