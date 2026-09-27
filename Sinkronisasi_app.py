import streamlit as st
import pandas as pd
import io

st.set_page_config(
    page_title="Sistem Sinkronisasi Master Data",
    page_icon="🔄",
    layout="wide"
)

st.title("🔄 Sistem Sinkronisasi & Pengecekan Master Data")
st.markdown("""
Aplikasi ini membantu Anda membandingkan, menganalisis perbedaan, mendeteksi duplikat, dan menyelaraskan dua file master data (File A dan File B).
Sistem ini menggunakan **Explicit Column Mapping** sehingga Anda bisa mencocokkan kolom dengan nama berbeda (misal: `ppoe username` di File A dengan `username` di File B).
""")

def find_matching_column(col_a, df_b_cols):
    """Mencari nama kolom di File B yang paling mirip dengan kolom di File A secara cerdas"""
    if col_a in df_b_cols:
        return col_a
    
    # 1. Case insensitive check
    for col_b in df_b_cols:
        if col_b.lower() == col_a.lower():
            return col_b
            
    # 2. String normalization check (tanpa spasi, underscore, strip)
    normalized_a = col_a.lower().replace(" ", "").replace("_", "").replace("-", "")
    for col_b in df_b_cols:
        normalized_b = col_b.lower().replace(" ", "").replace("_", "").replace("-", "")
        if normalized_a == normalized_b:
            return col_b
            
    # 3. Partial check
    for col_b in df_b_cols:
        if col_a.lower() in col_b.lower() or col_b.lower() in col_a.lower():
            return col_b
            
    return None

# Inisialisasi session state untuk menyimpan cache file upload & hasil kalkulasi
if "prev_file_a" not in st.session_state:
    st.session_state.prev_file_a = None
if "prev_file_b" not in st.session_state:
    st.session_state.prev_file_b = None

col1, col2 = st.columns(2)

df_a = None
df_b = None

with col1:
    st.subheader("📁 Upload Master Data A (Referensi/Sumber)")
    file_a = st.file_uploader("Pilih File A (CSV atau Excel)", type=["csv", "xlsx", "xls"], key="file_a")
    if file_a is not None:
        if file_a.name != st.session_state.prev_file_a:
            st.session_state.reconciliation_done = False
            st.session_state.prev_file_a = file_a.name
        try:
            if file_a.name.endswith('.csv'):
                df_a = pd.read_csv(file_a)
            else:
                df_a = pd.read_excel(file_a)
            df_a.columns = [str(c).strip() for c in df_a.columns]
            st.success(f"Berhasil memuat File A: {df_a.shape[0]} baris, {df_a.shape[1]} kolom")
            st.dataframe(df_a.head(5), use_container_width=True)
        except Exception as e:
            st.error(f"Gagal membaca File A: {e}")

with col2:
    st.subheader("📁 Upload Master Data B (Target/Pembanding)")
    file_b = st.file_uploader("Pilih File B (CSV atau Excel)", type=["csv", "xlsx", "xls"], key="file_b")
    if file_b is not None:
        if file_b.name != st.session_state.prev_file_b:
            st.session_state.reconciliation_done = False
            st.session_state.prev_file_b = file_b.name
        try:
            if file_b.name.endswith('.csv'):
                df_b = pd.read_csv(file_b)
            else:
                df_b = pd.read_excel(file_b)
            df_b.columns = [str(c).strip() for c in df_b.columns]
            st.success(f"Berhasil memuat File B: {df_b.shape[0]} baris, {df_b.shape[1]} kolom")
            st.dataframe(df_b.head(5), use_container_width=True)
        except Exception as e:
            st.error(f"Gagal membaca File B: {e}")

if df_a is not None and df_b is not None:
    st.markdown("---")
    st.header("⚙️ Pengaturan Sinkronisasi & Pemetaan Kolom")
    st.info("💡 Semua pilihan kolom di bawah ini mengacu pada kolom di **File A**. Sistem akan memetakan pasangannya ke File B secara manual maupun otomatis.")

    # Edukasi Pencocokan Kunci agar kasus AAN_LP tidak terulang
    st.warning("""
    ⚠️ **PENTING UNTUK REKONSILIASI AKURAT:**
    Untuk mencocokkan data agar berpasangan (seperti kasus `AAN_LP`), pilihlah **hanya 1 kolom unik saja** sebagai Kunci Utama (ID), misalnya **`PPPoE Username`**.
    Jangan memilih kolom `ID` database atau `NAS` sebagai Kunci Utama, karena jika nilainya berbeda di antara kedua file, sistem akan mengira data tersebut tidak memiliki pasangan.
    """)

    # Mencari rekomendasi satu kunci utama terbaik (mencari PPPoE Username dulu)
    suggested_keys = []
    for col in df_a.columns:
        if col.lower() in ['nas', 'username', 'ppoe username', 'id', 'key']:
            suggested_keys.append(col)
            
    col_setup1, col_setup2 = st.columns(2)
    
    with col_setup1:
        st.subheader("🔑 Kolom Kunci Unik (ID) dari File A")
        selected_keys = st.multiselect(
            "Pilih kolom kunci utama dari File A (misal: 'ppoe username', 'nas'):",
            options=list(df_a.columns),
            default=suggested_keys if len(suggested_keys) > 0 else []
        )
    
    with col_setup2:
        st.subheader("👤 Kolom Informasi Tambahan (Bukan Kunci)")
        info_cols_options = [col for col in df_a.columns if col not in selected_keys]
        suggested_info = [col for col in info_cols_options if 'nama' in col.lower() or 'name' in col.lower()]
        
        selected_info_cols = st.multiselect(
            "Pilih kolom tambahan dari File A untuk selalu ditampilkan di laporan (misal: 'nama'):",
            options=info_cols_options,
            default=suggested_info if suggested_info else []
        )
    
    if not selected_keys:
        st.warning("⚠️ Mohon pilih minimal satu kolom sebagai kunci unik untuk memulai proses pencocokan!")
    else:
        st.markdown("### 🔗 Hasil Penyelarasan Kolom Eksplisit (Hubungkan Kolom A ke Kolom B)")
        
        key_mapping = {}
        info_mapping = {}
        
        col_map_disp1, col_map_disp2 = st.columns(2)
        
        with col_map_disp1:
            st.markdown("**Pemetaan Kunci Utama (Wajib):**")
            for key in selected_keys:
                match = find_matching_column(key, df_b.columns)
                default_index = 0
                if match in list(df_b.columns):
                    default_index = list(df_b.columns).index(match)
                
                selected_b_key = st.selectbox(
                    f"Pilih pasangan di File B untuk kunci `{key}` (File A):",
                    options=list(df_b.columns),
                    index=default_index,
                    key=f"key_map_select_{key}"
                )
                key_mapping[key] = selected_b_key
                st.write(f"👉 `{key}` (File A) dipasangkan dengan `{selected_b_key}` (File B)")
                    
        with col_map_disp2:
            st.markdown("**Pemetaan Informasi Tambahan (Opsional):**")
            for info_col in selected_info_cols:
                match = find_matching_column(info_col, df_b.columns)
                options_b = ["-- Tidak Ada Pasangan --"] + list(df_b.columns)
                default_index = 0
                if match in list(df_b.columns):
                    default_index = options_b.index(match)
                
                selected_b_info = st.selectbox(
                    f"Pilih pasangan di File B untuk kolom `{info_col}` (File A):",
                    options=options_b,
                    index=default_index,
                    key=f"info_map_select_{info_col}"
                )
                if selected_b_info != "-- Tidak Ada Pasangan --":
                    info_mapping[info_col] = selected_b_info
                    st.write(f"👉 `{info_col}` (File A) dipasangkan dengan `{selected_b_info}` (File B)")
                else:
                    info_mapping[info_col] = None
                    st.write(f"ℹ️ `{info_col}` (File A) tidak ditampilkan dari File B")

        # Saring opsi kolom pembanding yang tersisa
        compare_cols_options = [
            col for col in df_a.columns 
            if col not in selected_keys 
            and col not in selected_info_cols
        ]
        
        selected_compare_cols = st.multiselect(
            "Pilih kolom data dari File A yang ingin diperiksa kesamaan nilainya:",
            options=compare_cols_options,
            default=compare_cols_options
        )
        
        compare_mapping = {}
        for comp_col in selected_compare_cols:
            match = find_matching_column(comp_col, df_b.columns)
            if match:
                compare_mapping[comp_col] = match

        # Salin data untuk pemrosesan internal
        df_a_processed = df_a.copy()
        df_b_processed = df_b.copy()
        
        # Buat kunci gabungan (Composite Key) berdasarkan pemetaan
        df_a_processed['_temp_composite_key'] = df_a_processed[selected_keys].astype(str).agg('-'.join, axis=1)
        
        mapped_keys_b = [key_mapping[k] for k in selected_keys]
        df_b_processed['_temp_composite_key'] = df_b_processed[mapped_keys_b].astype(str).agg('-'.join, axis=1)

        st.markdown("### 📋 Deteksi Awal Duplikasi Kunci")
        
        duplicates_a = df_a_processed[df_a_processed.duplicated(subset=['_temp_composite_key'], keep=False)]
        duplicates_b = df_b_processed[df_b_processed.duplicated(subset=['_temp_composite_key'], keep=False)]
        
        dup_col1, dup_col2 = st.columns(2)
        
        def clean_display_df(df):
            if '_temp_composite_key' in df.columns:
                return df.drop(columns=['_temp_composite_key'])
            return df
        
        with dup_col1:
            if not duplicates_a.empty:
                st.error(f"⚠️ Terdeteksi {len(duplicates_a)} baris terduplikat di **File A** berdasarkan kombinasi {selected_keys}!")
                with st.expander("Lihat Detail Data Duplikat File A"):
                    st.dataframe(clean_display_df(duplicates_a.sort_values(by=selected_keys)), use_container_width=True)
                    csv_dup_a = clean_display_df(duplicates_a).to_csv(index=False).encode('utf-8')
                    st.download_button("Unduh Data Duplikat File A (CSV)", csv_dup_a, "duplikat_file_A.csv", "text/csv")
            else:
                st.success(f"✅ Tidak ada data duplikat di **File A** (berdasarkan kombinasi {selected_keys}).")
                
        with dup_col2:
            if not duplicates_b.empty:
                st.error(f"⚠️ Terdeteksi {len(duplicates_b)} baris terduplikat di **File B** berdasarkan kombinasi {mapped_keys_b}!")
                with st.expander("Lihat Detail Data Duplikat File B"):
                    st.dataframe(clean_display_df(duplicates_b.sort_values(by=mapped_keys_b)), use_container_width=True)
                    csv_dup_b = clean_display_df(duplicates_b).to_csv(index=False).encode('utf-8')
                    st.download_button("Unduh Data Duplikat File B (CSV)", csv_dup_b, "duplikat_file_B.csv", "text/csv")
            else:
                st.success(f"✅ Tidak ada data duplikat di **File B** (berdasarkan kombinasi {mapped_keys_b}).")

        # Reset memori jika pengaturan kolom berubah
        current_settings = {
            "selected_keys": selected_keys,
            "selected_info_cols": selected_info_cols,
            "selected_compare_cols": selected_compare_cols,
            "key_mapping": key_mapping,
            "info_mapping": info_mapping
        }
        if "prev_settings" not in st.session_state:
            st.session_state.prev_settings = current_settings
        elif st.session_state.prev_settings != current_settings:
            st.session_state.reconciliation_done = False
            st.session_state.prev_settings = current_settings

        if st.button("🚀 Jalankan Pengecekan & Sinkronisasi", type="primary"):
            # Lakukan pembersihan duplikasi demi akurasi pencocokan
            if not duplicates_a.empty:
                df_a_clean = df_a_processed.drop_duplicates(subset=['_temp_composite_key'], keep='first')
            else:
                df_a_clean = df_a_processed.copy()
                
            if not duplicates_b.empty:
                df_b_clean = df_b_processed.drop_duplicates(subset=['_temp_composite_key'], keep='first')
            else:
                df_b_clean = df_b_processed.copy()

            # 1. Mencari data yang hanya ada di File A (Missing in B)
            only_in_a = df_a_clean[~df_a_clean['_temp_composite_key'].isin(df_b_clean['_temp_composite_key'])]
            
            # 2. Mencari data yang hanya ada di File B (Missing in A)
            only_in_b = df_b_clean[~df_b_clean['_temp_composite_key'].isin(df_a_clean['_temp_composite_key'])]

            # 3. Konsolidasi Data yang Tidak Berpasangan (Symmetric Difference)
            df_unmatched_all = pd.DataFrame()
            
            if not only_in_a.empty:
                temp_a = only_in_a.copy()
                temp_a.insert(0, 'Status Keberadaan', 'Hanya Ada di File A (Hilang di B)')
                df_unmatched_all = pd.concat([df_unmatched_all, temp_a], ignore_index=True)
                
            if not only_in_b.empty:
                temp_b = only_in_b.copy()
                # Ubah nama kolom kunci di File B agar sejajar dengan File A saat digabungkan
                rename_dict = {}
                for k, v in key_mapping.items():
                    rename_dict[v] = k
                for k, v in info_mapping.items():
                    if v:
                        rename_dict[v] = k
                
                temp_b = temp_b.rename(columns=rename_dict)
                temp_b.insert(0, 'Status Keberadaan', 'Hanya Ada di File B (Hilang di A)')
                df_unmatched_all = pd.concat([df_unmatched_all, temp_b], ignore_index=True)

            # 4. Mencari data yang ada di kedua file tapi ada perbedaan nilai kolom
            common_ids = set(df_a_clean['_temp_composite_key']).intersection(set(df_b_clean['_temp_composite_key']))
            
            shared_a = df_a_clean[df_a_clean['_temp_composite_key'].isin(common_ids)].set_index('_temp_composite_key')
            shared_b = df_b_clean[df_b_clean['_temp_composite_key'].isin(common_ids)].set_index('_temp_composite_key')
            
            mismatched_rows = []
            
            for idx in common_ids:
                row_a = shared_a.loc[idx]
                row_b = shared_b.loc[idx]
                
                diff_dict = {}
                for key_col in selected_keys:
                    diff_dict[key_col] = row_a[key_col]
                for info_col in selected_info_cols:
                    diff_dict[info_col] = row_a[info_col]
                    
                has_difference = False
                
                for col_a in selected_compare_cols:
                    col_b = compare_mapping.get(col_a)
                    if not col_b or col_b not in row_b.index:
                        continue
                        
                    val_a = str(row_a[col_a]).strip() if pd.notna(row_a[col_a]) else ""
                    val_b = str(row_b[col_b]).strip() if pd.notna(row_b[col_b]) else ""
                    
                    if val_a != val_b:
                        diff_dict[f"{col_a} (File A)"] = row_a[col_a]
                        diff_dict[f"{col_b} (File B)"] = row_b[col_b]
                        has_difference = True
                
                if has_difference:
                    mismatched_rows.append(diff_dict)
                    
            df_mismatched = pd.DataFrame(mismatched_rows)

            # 5. Membuat master gabungan (A dijadikan acuan utama)
            df_merged = df_a_clean.copy()
            if not only_in_b.empty:
                rename_dict_merged = {v: k for k, v in key_mapping.items()}
                for k, v in info_mapping.items():
                    if v:
                        rename_dict_merged[v] = k
                only_in_b_aligned = only_in_b.rename(columns=rename_dict_merged)
                df_merged = pd.concat([df_merged, only_in_b_aligned], ignore_index=True)

            # Kunci seluruh hasil ke memori session state
            st.session_state.reconciliation_done = True
            st.session_state.df_unmatched_all = df_unmatched_all
            st.session_state.only_in_a = only_in_a
            st.session_state.only_in_b = only_in_b
            st.session_state.df_mismatched = df_mismatched
            st.session_state.df_merged = df_merged
            st.session_state.duplicates_a = duplicates_a
            st.session_state.duplicates_b = duplicates_b
            st.session_state.saved_keys = selected_keys
            st.session_state.saved_info_cols = selected_info_cols
            st.session_state.saved_key_mapping = key_mapping
            st.session_state.saved_info_mapping = info_mapping

        if st.session_state.get('reconciliation_done', False):
            # Load hasil kalkulasi yang tersimpan di memori
            df_unmatched_all = st.session_state.df_unmatched_all
            only_in_a = st.session_state.only_in_a
            only_in_b = st.session_state.only_in_b
            df_mismatched = st.session_state.df_mismatched
            df_merged = st.session_state.df_merged
            duplicates_a = st.session_state.duplicates_a
            duplicates_b = st.session_state.duplicates_b
            selected_keys = st.session_state.saved_keys
            selected_info_cols = st.session_state.saved_info_cols
            key_mapping = st.session_state.saved_key_mapping
            info_mapping = st.session_state.saved_info_mapping

            st.markdown("---")
            st.header("📊 Laporan Hasil Rekonsiliasi")
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric(label="Hanya di File A", value=len(only_in_a))
            m2.metric(label="Hanya di File B", value=len(only_in_b))
            m3.metric(label="Total Data Unmatched", value=len(df_unmatched_all))
            m4.metric(label="Data Berbeda Nilai", value=len(df_mismatched))

            tab_unmatched_combined, tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "❌ Semua Data Tidak Sinkron (Unmatched)",
                "🔍 Hanya di File A", 
                "🔍 Hanya di File B", 
                "⚠️ Perbedaan Nilai Kolom",
                "📋 Log Duplikat yang Ditemukan",
                "💾 Hasil Sinkronisasi (Master Bersih)"
            ])

            # Mengurutkan kolom visual agar kunci utama dan info diletakkan di paling kiri (depan)
            def rearrange_cols(df, first_cols):
                if df.empty:
                    return df
                cols = list(df.columns)
                lead_cols = [c for c in first_cols if c in cols]
                remaining_cols = [c for c in cols if c not in lead_cols]
                return df[lead_cols + remaining_cols]

            front_cols = ['Status Keberadaan'] + selected_keys + selected_info_cols

            with tab_unmatched_combined:
                st.subheader("Semua Data yang Tidak Ada di Salah Satu File")
                st.markdown(f"""
                Daftar gabungan semua baris data yang **tidak memiliki pasangan kunci ({', '.join(selected_keys)})** di file lawannya. 
                Kolom **{', '.join(selected_info_cols)}** ikut ditampilkan agar Anda bisa mengidentifikasi pemilik data dengan mudah.
                """)
                if not df_unmatched_all.empty:
                    filter_status = st.selectbox(
                        "Saring tampilan berdasarkan status:",
                        options=["Tampilkan Semua", "Hanya Ada di File A (Hilang di B)", "Hanya Ada di File B (Hilang di A)"],
                        key="filter_unmatched_state"
                    )
                    
                    if filter_status != "Tampilkan Semua":
                        filtered_df = df_unmatched_all[df_unmatched_all['Status Keberadaan'] == filter_status]
                    else:
                        filtered_df = df_unmatched_all

                    df_unmatched_display = rearrange_cols(clean_display_df(filtered_df), front_cols)
                    st.dataframe(df_unmatched_display, use_container_width=True)
                    
                    csv_unmatched = df_unmatched_display.to_csv(index=False).encode('utf-8')
                    file_name_download = "unmatched_filtered.csv" if filter_status != "Tampilkan Semua" else "semua_data_unmatched.csv"
                    st.download_button(
                        label=f"📥 Unduh Hasil Filter: {filter_status} (CSV)", 
                        data=csv_unmatched, 
                        file_name=file_name_download, 
                        mime="text/csv"
                    )
                else:
                    st.success("🎉 Sempurna! Semua kombinasi ID data di File A dan File B saling berpasangan satu sama lain.")

            with tab1:
                st.subheader("Data yang hanya ada di File A")
                if not only_in_a.empty:
                    df_only_a_display = rearrange_cols(clean_display_df(only_in_a), selected_keys + selected_info_cols)
                    st.dataframe(df_only_a_display, use_container_width=True)
                    csv_a = df_only_a_display.to_csv(index=False).encode('utf-8')
                    st.download_button("Unduh Data Hanya di A (CSV)", csv_a, "hanya_di_A.csv", "text/csv")
                else:
                    st.info("Semua data di File A juga ada di File B.")

            with tab2:
                st.subheader("Data yang hanya ada di File B")
                if not only_in_b.empty:
                    # Sejajarkan nama kolom kunci di File B untuk kebutuhan tampilan visual
                    rename_dict_b = {v: k for k, v in key_mapping.items()}
                    for k, v in info_mapping.items():
                        if v:
                            rename_dict_b[v] = k
                    only_in_b_display = only_in_b.rename(columns=rename_dict_b)
                    
                    df_only_b_display = rearrange_cols(clean_display_df(only_in_b_display), selected_keys + selected_info_cols)
                    st.dataframe(df_only_b_display, use_container_width=True)
                    csv_b = df_only_b_display.to_csv(index=False).encode('utf-8')
                    st.download_button("Unduh Data Hanya di B (CSV)", csv_b, "hanya_di_B.csv", "text/csv")
                else:
                    st.info("Semua data di File B juga ada di File A.")

            with tab3:
                st.subheader("Perbandingan Nilai Kolom yang Berbeda")
                if not df_mismatched.empty:
                    df_mismatched_display = rearrange_cols(df_mismatched, selected_keys + selected_info_cols)
                    st.dataframe(df_mismatched_display, use_container_width=True)
                    csv_diff = df_mismatched_display.to_csv(index=False).encode('utf-8')
                    st.download_button("Unduh Laporan Perbedaan (CSV)", csv_diff, "perbedaan_nilai.csv", "text/csv")
                else:
                    st.success("Hebat! Tidak ada perbedaan nilai pada kolom yang Anda bandingkan untuk data yang sama.")

            with tab4:
                st.subheader("Log Rekaman Data Duplikat")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.markdown("**Duplikat di File A:**")
                    if not duplicates_a.empty:
                        df_dup_a_display = rearrange_cols(clean_display_df(duplicates_a), selected_keys + selected_info_cols)
                        st.dataframe(df_dup_a_display, use_container_width=True)
                    else:
                        st.write("Tidak ada duplikat.")
                with col_d2:
                    st.markdown("**Duplikat di File B:**")
                    if not duplicates_b.empty:
                        rename_dup_b = {v: k for k, v in key_mapping.items()}
                        for k, v in info_mapping.items():
                            if v:
                                rename_dup_b[v] = k
                        duplicates_b_display = duplicates_b.rename(columns=rename_dup_b)
                        df_dup_b_display = rearrange_cols(clean_display_df(duplicates_b_display), selected_keys + selected_info_cols)
                        st.dataframe(df_dup_b_display, use_container_width=True)
                    else:
                        st.write("Tidak ada duplikat.")

            with tab5:
                st.subheader("Master Data Gabungan Hasil Sinkronisasi")
                st.markdown(f"""
                **Aturan Penggabungan (Sinkronisasi):**
                1. Mengambil semua data unik berdasarkan kunci kombinasi ({', '.join(selected_keys)}) dari **File A (Clean)** dan **File B (Clean)**.
                2. Jika ada data dengan ID yang sama tetapi nilainya berbeda, aplikasi ini memprioritaskan nilai dari **File A (Referensi Utama)**.
                """)
                
                df_merged_display = rearrange_cols(clean_display_df(df_merged), selected_keys + selected_info_cols)
                st.dataframe(df_merged_display, use_container_width=True)
                st.write(f"Total baris setelah disinkronkan: **{len(df_merged_display)} baris**")
                
                csv_merged = df_merged_display.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Unduh Master Data Hasil Sinkronisasi (CSV)",
                    data=csv_merged,
                    file_name="master_data_disinkronkan.csv",
                    mime="text/csv"
                )
else:
    st.info("💡 Silakan unggah kedua file master data di atas untuk memulai analisis.")