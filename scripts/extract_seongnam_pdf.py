"""성남시 대형폐기물 수수료 기준(별표 1) PDF -> CSV 초안.
사용: python scripts/extract_seongnam_pdf.py <입력.pdf> <출력.csv>
결과는 반드시 원문 PDF와 대조해 검수해야 한다(check_status 열)."""
import sys, csv, re
import pdfplumber

def clean(x):
    return re.sub(r"\s+", " ", (x or "").replace("\n", " ")).strip()

def main(src, dst):
    rows, cat, name = [], "", ""
    with pdfplumber.open(src) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            for table in page.extract_tables():
                for r in table:
                    if not r or clean(r[0]) == "종별":
                        continue
                    c0, c1, c2, c3 = (clean(r[i]) if len(r) > i else "" for i in range(4))
                    c4 = clean(r[4]) if len(r) > 4 else ""
                    if c0:
                        cat = c0.replace(" ", "")
                    if c1:
                        name = c1
                    if not c2 and not c3:
                        continue
                    fee = c3.replace(",", "")
                    if fee.isdigit():
                        ftype, won = "paid", int(fee)
                    elif "면제" in fee:
                        ftype, won = "exempt", 0
                    else:
                        ftype, won = "unknown", ""
                    rows.append([cat, name, c2, c3, ftype, won, c4, pno, "미검수"])
    with open(dst, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["category", "item_name", "spec", "fee_raw", "fee_type", "fee_won", "note", "pdf_page", "check_status"])
        w.writerows(rows)
    print(len(rows), "rows ->", dst)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
