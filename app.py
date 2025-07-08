import streamlit as st
import pandas as pd
import pdfplumber
import io
import re
import hashlib

# ========================
# Fungsi: Temukan Tanggal
# ========================
def find_invoice_date(pdf_file):
    month_map = {
        "Januari": "01", "Februari": "02", "Maret": "03", "April": "04", "Mei": "05", "Juni": "06", 
        "Juli": "07", "Agustus": "08", "September": "09", "Oktober": "10", "November": "11", "Desember": "12"
    }
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                match = re.search(r'\b(\d{1,2})\s*(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s*(\d{4})\b', text, re.IGNORECASE)
                if match:
                    day, month, year = match.groups()
                    return f"{day.zfill(2)}/{month_map[month]}/{year}"
    return "Tidak ditemukan"

# ========================
# Fungsi: Ekstraksi PDF (dengan Laporan Kegagalan)
# ========================
def extract_data_from_pdf(pdf_file, tanggal_faktur):
    data = []
    failed_blocks = [] # Daftar untuk menyimpan data yang gagal
    no_fp, nama_penjual, nama_pembeli = None, None, None

    with pdfplumber.open(pdf_file) as pdf:
        first_page_text = pdf.pages[0].extract_text() if pdf.pages else ""
        if first_page_text:
            no_fp_match = re.search(r'Kode dan Nomor Seri Faktur Pajak\s*:\s*([\d\.\-]+)', first_page_text)
            if no_fp_match: no_fp = no_fp_match.group(1)
            penjual_match = re.search(r'Nama\s*:\s*(SOFIE FASHION INDONESIA)', first_page_text, re.DOTALL)
            if penjual_match: nama_penjual = penjual_match.group(1).strip()
            pembeli_match = re.search(r'Pembeli.*?Nama\s*:\s*(.+?)\s*Alamat', first_page_text, re.DOTALL)
            if pembeli_match:
                nama_pembeli = pembeli_match.group(1).strip()
                nama_pembeli = re.sub(r'\bAlamat\b', '', nama_pembeli, flags=re.IGNORECASE).strip()

        all_rows = []
        for page in pdf.pages:
            table = page.extract_table(table_settings={"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            if table: all_rows.extend(table)
        
        item_blocks, current_block = [], []
        for row in all_rows:
            if not row or not any(cell and str(cell).strip() for cell in row): continue
            item_no_match = re.match(r'^\s*(\d+)', str(row[0]).strip())
            is_likely_item_start = item_no_match and (not row[1] or str(row[1]).strip().isdigit())
            if is_likely_item_start:
                if current_block: item_blocks.append(current_block)
                current_block = [row]
            else:
                if current_block: current_block.append(row)
        if current_block: item_blocks.append(current_block)
            
        for block in item_blocks:
            block_text = " ".join(" ".join(filter(None, [str(c).strip().replace('\n', ' ') for c in r])) for r in block)
            harga_qty_match = re.search(r'Rp\s*~?\$?p?\s*([\d.,]+)\s*x\s*([\d.,]+)\s*(\w+)', block_text, re.IGNORECASE)

            if harga_qty_match:
                # Proses data yang berhasil...
                nama_barang = re.sub(r'Rp\s*~?\$?p?\s*([\d.,]+).*', '', block_text, flags=re.IGNORECASE)
                nama_barang = re.sub(r'^\d+\s*[\d\w-]*\s*', '', nama_barang)
                nama_barang = re.sub(r'Potongan Harga.*|PPnBM.*', '', nama_barang, flags=re.DOTALL)
                nama_barang = ' '.join(nama_barang.split())
                harga = float(harga_qty_match.group(1).replace('.', '').replace(',', '.'))
                qty = float(harga_qty_match.group(2).replace('.', '').replace(',', '.'))
                unit = harga_qty_match.group(3)
                potongan_match = re.search(r'Potongan Harga\s*=\s*Rp\s*([\d.,]+)', block_text)
                potongan = float(potongan_match.group(1).replace('.', '').replace(',', '.')) if potongan_match else 0.0
                total = (harga * qty) - potongan
                dpp = total / 1.11
                ppn = total - dpp
                data.append([
                    no_fp or "Tidak ditemukan", nama_penjual or "Tidak ditemukan", nama_pembeli or "Tidak ditemukan",
                    tanggal_faktur, nama_barang, qty, unit, harga, potongan, total, round(dpp, 2), round(ppn, 2)
                ])
            else:
                # Jika tidak ditemukan pola harga, anggap gagal dan simpan teksnya
                failed_blocks.append(block_text)

    return data, failed_blocks
    
# ========================
# Fungsi: Halaman Login
# ========================
def login_page():
    users = {
        "user1": hashlib.sha256("ijfugroup1".encode()).hexdigest(),
        "user2": hashlib.sha256("ijfugroup2".encode()).hexdigest(),
        "user3": hashlib.sha256("ijfugroup3".encode()).hexdigest(),
        "user4": hashlib.sha256("ijfugroup4".encode()).hexdigest()
    }

    st.title("Login Convert PDF FP To Excel")
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Masukkan username")
        password = st.text_input("Password", type="password", placeholder="Masukkan password")
        login_btn = st.form_submit_button("Login")

    if login_btn:
        if username in users and hashlib.sha256(password.encode()).hexdigest() == users[username]:
            st.session_state["logged_in"] = True
            st.success("Login berhasil!")
            st.rerun()
        else:
            st.error("Username atau password salah.")

# ========================
# Fungsi: Halaman Utama (dengan Notifikasi Kegagalan)
# ========================
def main_app():
    st.title("Convert Faktur Pajak PDF To Excel")

    if st.button("Logout"):
        st.session_state["logged_in"] = False
        st.session_state["unduh_selesai"] = False
        st.rerun()

    if "unduh_selesai" not in st.session_state:
        st.session_state["unduh_selesai"] = False

    if st.session_state["unduh_selesai"]:
        st.success("✅ File berhasil diunduh. Silakan upload faktur baru.")
        if st.button("🔁 Upload Data Baru"):
            st.session_state["unduh_selesai"] = False
            st.rerun()
        return

    uploaded_files = st.file_uploader("📄 Upload Faktur Pajak (PDF, bisa lebih dari satu)", type=["pdf"], accept_multiple_files=True)

    if uploaded_files:
        all_data = []
        all_failed_blocks = []
        for file in uploaded_files:
            try:
                tanggal = find_invoice_date(file)
                # Terima dua nilai kembalian dari fungsi
                data, failed_blocks = extract_data_from_pdf(file, tanggal)
                if data:
                    all_data.extend(data)
                if failed_blocks:
                    all_failed_blocks.extend(failed_blocks)
            except Exception as e:
                st.error(f"Gagal memproses {file.name}: {e}")

        # Tampilkan notifikasi jika ada data yang gagal
        if all_failed_blocks:
            st.warning("⚠️ Beberapa data item tidak dapat dibaca dan kemungkinan terlewat.")
            with st.expander("Klik untuk melihat detail data yang gagal dibaca"):
                for i, block_text in enumerate(all_failed_blocks):
                    st.text_area(f"Data Gagal #{i+1}", block_text, height=100, key=f"failed_{i}")

        if all_data:
            df = pd.DataFrame(all_data, columns=[
                "No FP", "Nama Penjual", "Nama Pembeli", "Tanggal Faktur",
                "Nama Barang", "Qty", "Satuan", "Harga", "Potongan", "Total", "DPP", "PPN"
            ])
            df.index += 1
            st.write("### 🧾 Pratinjau Data Berhasil")
            st.dataframe(df)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=True, sheet_name='Faktur Pajak')
            output.seek(0)

            if st.download_button(
                label="📥 Unduh Excel",
                data=output,
                file_name="Faktur_Pajak.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ):
                st.session_state["unduh_selesai"] = True
                st.rerun()
        elif not all_failed_blocks:
            st.info("Tidak ada data yang dapat diekstrak dari file yang diunggah.")

# ========================
# Tombol Reset Debug
# ========================
if st.sidebar.button("🧹 Reset Session (Debug)"):
    st.session_state.clear()
    st.rerun()
