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
# Fungsi: Ekstraksi PDF
# ========================
def extract_data_from_pdf(pdf_file, tanggal_faktur):
    data = []
    no_fp, nama_penjual, nama_pembeli = None, None, None
    pending_item_name = ""

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                if not no_fp:
                    no_fp_match = re.search(r'Kode dan Nomor Seri Faktur Pajak\s*:\s*([\d\.\-]+)', text)
                    if no_fp_match:
                        no_fp = no_fp_match.group(1)

                if not nama_penjual:
                    penjual_match = re.search(r'Nama\s*:\s*(SOFIE FASHION INDONESIA)', text, re.DOTALL)
                    if penjual_match:
                        nama_penjual = penjual_match.group(1).strip()

                if not nama_pembeli:
                    pembeli_match = re.search(r'Pembeli.*?Nama\s*:\s*(.+?)\s*Alamat', text, re.DOTALL)
                    if pembeli_match:
                        nama_pembeli = pembeli_match.group(1).strip()
                        nama_pembeli = re.sub(r'\bAlamat\b', '', nama_pembeli, flags=re.IGNORECASE).strip()

            table = page.extract_table()
            if table:
                for row in table:
                    if not row or not any(cell for cell in row if cell and cell.strip()):
                        continue
                    
                    row_text = " ".join(filter(None, [str(c).strip() for c in row]))
                    
                    # Regex untuk mencari pola harga x kuantitas
                    harga_qty_match = re.search(r'Rp\s*~?\$?p?\s*([\d.,]+)\s*x\s*([\d.,]+)\s*(\w+)', row_text, re.IGNORECASE)

                    if harga_qty_match:
                        # Baris ini berisi harga, jadi kita proses sebagai item
                        
                        # Gabungkan nama yang tertunda dengan nama di baris saat ini
                        current_name_part = re.sub(r'Rp\s*~?\$?p?\s*([\d.,]+).*', '', row_text, flags=re.IGNORECASE).strip()
                        current_name_part = re.sub(r'^\d+\s*[\d\w-]*\s*', '', current_name_part).strip() # Hapus nomor dan kode barang
                        
                        full_item_name = (pending_item_name + " " + current_name_part).strip()
                        
                        # Bersihkan teks sisa
                        full_item_name = re.sub(r'Potongan Harga.*|PPnBM.*', '', full_item_name, flags=re.DOTALL).strip()
                        
                        harga = float(harga_qty_match.group(1).replace('.', '').replace(',', '.'))
                        qty = float(harga_qty_match.group(2).replace('.', '').replace(',', '.'))
                        unit = harga_qty_match.group(3)
                        
                        potongan_match = re.search(r'Potongan Harga\s*=\s*Rp\s*([\d.,]+)', row_text)
                        potongan = float(potongan_match.group(1).replace('.', '').replace(',', '.')) if potongan_match else 0.0
                        
                        # Ekstrak total langsung dari kolom terakhir jika ada, jika tidak, hitung
                        total_str = row[-1].replace('.', '').replace(',', '.')
                        total = float(total_str) if re.match(r'^\d+\.\d+$', total_str) else (harga * qty) - potongan

                        # Perhitungan DPP & PPN mungkin perlu disesuaikan dengan aturan pajak (misal 11%)
                        # Berdasarkan file PDF: PPN adalah 11% dari DPP
                        dpp = total / 1.11
                        ppn = total - dpp

                        data.append([
                            no_fp or "Tidak ditemukan",
                            nama_penjual or "Tidak ditemukan",
                            nama_pembeli or "Tidak ditemukan",
                            tanggal_faktur,
                            full_item_name,
                            qty,
                            unit,
                            harga,
                            potongan,
                            total,
                            round(dpp, 2),
                            round(ppn, 2)
                        ])
                        
                        pending_item_name = "" # Reset setelah item diproses

                    elif row[2] and not re.match(r'^\d+$', str(row[0])):
                        # Baris ini sepertinya hanya berisi nama barang, simpan untuk baris berikutnya
                        pending_item_name += " " + str(row[2]).strip()
    return data

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
# Fungsi: Halaman Utama
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
        for file in uploaded_files:
            try:
                tanggal = find_invoice_date(file)
                data = extract_data_from_pdf(file, tanggal)
                all_data.extend(data)
            except Exception as e:
                st.error(f"Gagal memproses {file.name}: {e}")

        if all_data:
            df = pd.DataFrame(all_data, columns=[
                "No FP", "Nama Penjual", "Nama Pembeli", "Tanggal Faktur",
                "Nama Barang", "Qty", "Satuan", "Harga", "Potongan", "Total", "DPP", "PPN"
            ])
            df.index += 1

            st.write("### 🧾 Pratinjau Data")
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

# ========================
# Kontrol Aplikasi
# ========================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login_page()
else:
    main_app()

# ========================
# Tombol Reset Debug
# ========================
if st.sidebar.button("🧹 Reset Session (Debug)"):
    st.session_state.clear()
    st.rerun()
