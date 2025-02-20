import streamlit as st
import pandas as pd
import pdfplumber
import io
import re
import hashlib

def find_invoice_date(pdf_file):
    """Mencari tanggal faktur dalam PDF, mulai dari halaman pertama."""
    month_map = {
        "Januari": "01", "Februari": "02", "Maret": "03", "April": "04", "Mei": "05", "Juni": "06", 
        "Juli": "07", "Agustus": "08", "September": "09", "Oktober": "10", "November": "11", "Desember": "12"
    }
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                date_match = re.search(r'(\d{1,2})\s*(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s*(\d{4})', text, re.IGNORECASE)
                if date_match:
                    day, month, year = date_match.groups()
                    return f"{day.zfill(2)}/{month_map[month]}/{year}"
    return "Tidak ditemukan"

def count_items_in_pdf(pdf_file):
    """Menghitung jumlah item dalam PDF berdasarkan pola nomor urut."""
    item_count = 0
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                matches = re.findall(r'^(\d{1,3})\s+000000', text, re.MULTILINE)
                item_count += len(matches)
    return item_count

def extract_data_from_pdf(pdf_file, tanggal_faktur, expected_item_count):
    data = []
    no_fp, nama_penjual, nama_pembeli = None, None, None
    item_counter = 0
    
    with pdfplumber.open(pdf_file) as pdf:
        previous_row = None
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                no_fp_match = re.search(r'Kode dan Nomor Seri Faktur Pajak:\s*(\d+)', text)
                if no_fp_match:
                    no_fp = no_fp_match.group(1)
                
                penjual_match = re.search(r'Nama\s*:\s*([\w\s\-.,&()]+)\nAlamat', text)
                if penjual_match:
                    nama_penjual = penjual_match.group(1).strip()
                
                pembeli_match = re.search(r'Pembeli Barang Kena Pajak/Penerima Jasa Kena Pajak:\s*Nama\s*:\s*([\w\s\-.,&()]+)\nAlamat', text)
                if pembeli_match:
                    nama_pembeli = pembeli_match.group(1).strip()
                    nama_pembeli = re.sub(r'\bAlamat\b', '', nama_pembeli, flags=re.IGNORECASE).strip()
            
            table = page.extract_table()
            if table:
                for row in table:
                    if len(row) >= 4 and row[0].isdigit():
                        if previous_row and row[0] == "":
                            previous_row[3] += " " + " ".join(row[2].split("\n")).strip()
                            continue
                        
                        nama_barang = " ".join(row[2].split("\n")).strip()
                        nama_barang = re.sub(r'Rp [\d.,]+ x [\d.,]+ \w+', '', nama_barang)
                        nama_barang = re.sub(r'PPnBM \(\d+,?\d*%\) = Rp [\d.,]+', '', nama_barang)
                        nama_barang = re.sub(r'Potongan Harga = Rp [\d.,]+', '', nama_barang).strip()
                        
                        potongan_harga_match = re.search(r'Potongan Harga\s*=\s*Rp\s*([\d.,]+)', row[2])
                        potongan_harga = int(float(potongan_harga_match.group(1).replace('.', '').replace(',', '.'))) if potongan_harga_match else 0
                        
                        harga_qty_info = re.search(r'Rp ([\d.,]+) x ([\d.,]+) (\w+)', row[2])
                        if harga_qty_info:
                            harga = int(float(harga_qty_info.group(1).replace('.', '').replace(',', '.')))
                            qty = int(float(harga_qty_info.group(2).replace('.', '').replace(',', '.')))
                            unit = harga_qty_info.group(3)
                        else:
                            harga, qty, unit = 0, 0, "Unknown"
                        
                        total = (harga * qty) - potongan_harga
                        potongan_harga = min(potongan_harga, total)
                        
                        ppn = round(total * 0.11, 2)
                        dpp = total - ppn
                        
                        item = [no_fp if no_fp else "Tidak ditemukan", nama_penjual if nama_penjual else "Tidak ditemukan", nama_pembeli if nama_pembeli else "Tidak ditemukan", tanggal_faktur, nama_barang, qty, unit, harga, potongan_harga, total, dpp, ppn]
                        data.append(item)
                        previous_row = item
                        item_counter += 1
                        
                        if item_counter >= expected_item_count:
                            break  
    return data

def login_page():
    """Menampilkan halaman login."""
    
# Simulasi database pengguna dengan password yang di-hash
users = {
    "user1": hashlib.sha256("ijfugroup1".encode()).hexdigest(),
    "user2": hashlib.sha256("ijfugroup2".encode()).hexdigest(),
    "user3": hashlib.sha256("ijfugroup3".encode()).hexdigest(),
    "user4": hashlib.sha256("ijfugroup4".encode()).hexdigest()
}

st.title("Login Konversi Faktur Pajak")

# Input username dan password
username = st.text_input("Username", placeholder="Masukkan username Anda")
password = st.text_input("Password", type="password", placeholder="Masukkan password Anda")

# Tombol login
if st.button("Login"):
    if username in users and hashlib.sha256(password.encode()).hexdigest() == users[username]:
        st.session_state["logged_in"] = True
        st.session_state["username"] = username  # Simpan username di session state
        st.success("Login berhasil!")
        st.session_state["logged_in"] = True  # Set session state to logged in
    else:
        st.error("Username atau password salah")

def main_app():
    """Aplikasi utama setelah login."""
    st.title("Konversi Faktur Pajak PDF To Excel")
    
    # Tombol logout hanya tampil jika sudah login
    if st.session_state.get("logged_in", False):
        if st.button("Logout"):
            st.session_state["logged_in"] = False
            st.session_state["username"] = None
            st.experimental_rerun()  # Reload the app after logout
    
    uploaded_files = st.file_uploader("Upload Faktur Pajak (PDF, bisa lebih dari satu)", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_files:
        all_data = []
        for uploaded_file in uploaded_files:
            tanggal_faktur = find_invoice_date(uploaded_file)
            detected_item_count = count_items_in_pdf(uploaded_file)
            extracted_data = extract_data_from_pdf(uploaded_file, tanggal_faktur, detected_item_count)
            extracted_item_count = len(extracted_data)
            
            if detected_item_count != extracted_item_count and detected_item_count != 0:
                st.warning(f"Jumlah item tidak cocok untuk {uploaded_file.name}: Ditemukan {detected_item_count}, diekstrak {extracted_item_count}")
            
            if extracted_data:
                all_data.extend(extracted_data)
        
        if all_data:
            df = pd.DataFrame(all_data, columns=[
                "No FP", "Nama Penjual", "Nama Pembeli", "Tanggal Faktur", "Nama Barang", 
                "Qty", "Satuan", "Harga", "Potongan Harga", "Total", "DPP", "PPN"
            ])
            df.index = df.index + 1  
            
            st.write("### Pratinjau Data yang Diekstrak")
            st.dataframe(df)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=True, sheet_name='Faktur Pajak')
            output.seek(0)
            
            st.download_button(label="\U0001F4E5 Unduh Excel", data=output, file_name="Faktur_Pajak.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.error("Gagal mengekstrak data. Pastikan format faktur sesuai.")

if __name__ == "__main__":
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    
    if not st.session_state["logged_in"]:
        login_page()  # Tampilkan form login hanya jika belum login
    else:
        main_app()  # Tampilkan aplikasi utama setelah login
