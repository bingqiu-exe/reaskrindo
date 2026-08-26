import re
import io
import numpy as np
import pandas as pd
from django.core.exceptions import ValidationError

class AutoMappingServices:

    COLUMN_MAPPING = {
        'TANGGAL_AWAL': [
            'inception', 'tgl_awal', 'tanggal_awal', 'start_date', 
            'period of ins. awal', 'tanggal awal', 'inception date',
            'eff_date', 'effective_date', 'tgl_efektif', 'uw_date', 'date'
        ],
        'TANGGAL_AKHIR': [
            'expiry', 'tgl_akhir', 'tanggal_akhir', 'end_date', 
            'period of ins. akhir', 'tanggal akhir', 'expiry date'
        ],
        'UY': [
            'uy', 'underwriting_year', 'uw_year', 'uw year', 'uy_final', 'year', 'tahun'
        ],
        'COB': [
            'product', 'product_name', 'produk', 'nama_produk', 
            'cob', 'class_of_business', 'toc', 'type_of_cover', 
            'line_of_business', 'lob', 'nama produk'
        ],
        'PRODUCT_ID': [
            'product_id', 'id_product', 'kd_produk', 'kode_produk', 'kode', 'kd'
        ],
        'TREATY_SCHEME_ID': [
            'treaty_scheme_id', 'primary_key', 'pk', 'key', 'kode_uy', 'pk_key'
        ],
        'COB_TREATY': [
            'cob_treaty', 'treaty_cob', 'cob reas', 'target_cob', 
            'cob_group', 'group_cob', 'cob_final', 'product_name'
        ]
    }
    
    MAPPING_COB_KEYWORDS = [
        'WELCAR INSURANCE', 'Onshore Property', 'PSAGBI / Polis Standard Asuransi Gempa Bumi Indonesia', 
        'Offshore Property', 'Comprehensive Machinery Insurance', 'CECR / Civil Engineering Completed Risk', 
        'CAR / Contractor All Risk', 'PAR / Property All Risk', 'Marine Hull', 'Machinery Breakdown',
        'IAR / Industrial All Risk', 'CPME / Contractor Plan Machinery and Equipment', 
        'Port and Terminal Liability', 'Sepeda Motor', 'Kendaraan Penumpang', 'Heavy Equipment', 
        'Aviation Hull', 'Kendaraan Pengangkut Barang', 'Fidelity Guarantee', 'Wreck Removal', 
        'PA Plus Debitur Bank Non KUR', 'PSAKI / Polis Standard Asuransi Kebakaran Indonesia', 
        'Electronic Equipment', 'Aviation Loss of License', 'Public Liability', 'PA Plus Debitur KUR', 
        'EAR / Erection All Risk', 'Livestock Insurance', 'PA / Personnal Accident', 'Airport Liability', 
        'Cash in Transit', 'Cash in ATM', 'Burglary Insurance and Theft', 'Comprehensive General Liability', 
        'PA Plus Santunan', 'Marine Cargo Export', 'Cash in Safe', 'Marine Cargo Domestik', 
        'Aviation Premises Liabilities & Hangar Keeper', 'Asuransi Mikro Usahaku', 
        'Asuransi Kecelakaan Diri Xtra', 'Marine Cargo Import', 'COMMERCIAL CREDIT', 
        'CONSUMPTIVE CREDIT', 'PRODUCTIVE CREDIT', 'SMALL CREDIT', 'SURETY BOND', 
        'Kontra Bank Garansi', 'COUNTER BANK GUARANTEE', 'Asuransi Kredit Perdagangan', 
        'Kredit Usaha Kecil Konvensional'
    ]

    @classmethod
    def _read_file(cls, uploaded_file, sheet_name=None) -> pd.DataFrame:
        """Reads file data supporting distinct Excel sheet targeting."""
        filename = uploaded_file.name.lower()
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)

        if filename.endswith('.csv'):
            encodings = ['utf-8-sig', 'cp1252', 'latin1', 'iso-8859-1']
            separators = [None, ';', ',', '\t']
            for enc in encodings:
                for sep in separators:
                    try:
                        df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc, sep=sep, engine='python')
                        if len(df.columns) > 1 or sep == separators[-1]:
                            return df
                    except Exception:
                        continue
            return pd.read_csv(io.BytesIO(file_bytes), encoding='latin1', engine='python')
        
        elif filename.endswith(('.xls', '.xlsx')):
            target_sheet = sheet_name if sheet_name is not None else 0
            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=target_sheet)
            
            if df.columns[0].startswith('Unnamed:'):
                for i, row in df.iterrows():
                    row_str = row.astype(str).str.lower().values
                    if any(any(alias in str(val) for alias in cls.COLUMN_MAPPING['TANGGAL_AWAL']) for val in row_str):
                        df.columns = df.iloc[i]
                        df = df.iloc[i+1:].reset_index(drop=True)
                        break
            return df

    @classmethod
    def _find_column(cls, df: pd.DataFrame, possible_names: list) -> str:
        """Finds column matching alias exact clean name or substring."""
        normalized_cols = {
            re.sub(r'[\s_\-/]+', '', str(col).replace('\xa0', ' ')).strip().lower(): col 
            for col in df.columns
        }
        
        for alias in possible_names:
            alias_clean = re.sub(r'[\s_\-/]+', '', alias).strip().lower()
            if alias_clean in normalized_cols:
                return normalized_cols[alias_clean]

        for alias in possible_names:
            alias_clean = re.sub(r'[\s_\-/]+', '', alias).strip().lower()
            if not alias_clean:
                continue
            for col_clean, original_col in normalized_cols.items():
                if alias_clean in col_clean or (len(col_clean) > 2 and col_clean in alias_clean):
                    return original_col
        return None

    @classmethod
    def calculate_uy_final(cls, date_series: pd.Series) -> pd.Series:
        """Evaluates inception date series according to cutoff rules."""
        dates = pd.to_datetime(date_series, errors='coerce', dayfirst=True)

        conditions = [
            dates < pd.Timestamp('2004-01-01'), dates < pd.Timestamp('2005-01-01'),
            dates < pd.Timestamp('2006-01-01'), dates < pd.Timestamp('2007-01-01'),
            dates < pd.Timestamp('2008-01-01'), dates < pd.Timestamp('2009-01-01'),
            dates < pd.Timestamp('2010-01-01'), dates < pd.Timestamp('2011-01-01'),
            dates < pd.Timestamp('2012-01-01'), dates < pd.Timestamp('2013-01-01'),
            dates < pd.Timestamp('2014-01-01'), dates < pd.Timestamp('2015-01-01'),
            dates < pd.Timestamp('2016-01-01'), dates < pd.Timestamp('2016-11-01'),
            dates < pd.Timestamp('2017-11-01'), dates < pd.Timestamp('2018-11-01'),
            dates < pd.Timestamp('2020-01-01'), dates < pd.Timestamp('2021-01-01'),
            dates < pd.Timestamp('2022-01-01'), dates < pd.Timestamp('2023-01-01'),
            dates < pd.Timestamp('2024-01-01'), dates < pd.Timestamp('2025-01-01'),
            dates < pd.Timestamp('2026-01-01'), dates < pd.Timestamp('2027-01-01'),
        ]

        choices = [
            "", "2004", "2005", "2006", "2007", "2008", "2009", "2010",
            "2011", "2012", "2013", "2014", "2015", "2016", "2016/2017",
            "2017/2018", "2018/2019", "2020", "2021", "2022", "2023",
            "2024", "2025", "2026"
        ]

        result = np.select(conditions, choices, default="")
        return pd.Series(result, index=date_series.index)

    @classmethod
    def _detect_cob_column(cls, df: pd.DataFrame) -> str:
        """Detects product/COB column via header alias or content scanning."""
        matched_col = cls._find_column(df, cls.COLUMN_MAPPING['COB'])
        if matched_col:
            return matched_col

        for col in df.columns:
            sample_vals = df[col].dropna().astype(str).str.lower().head(100)
            matches = sample_vals.apply(lambda val: any(kw.lower() in val for kw in cls.MAPPING_COB_KEYWORDS))
            if matches.sum() > 3:
                return col

        return None

    @classmethod
    def _detect_product_id_column(cls, df: pd.DataFrame) -> str:
        """Detects PRODUCT_ID column (khusus data Finance/Kode)."""
        return cls._find_column(df, cls.COLUMN_MAPPING['PRODUCT_ID'])

    @classmethod
    def _clean_code(cls, series: pd.Series) -> pd.Series:
        """Helper to sanitize product codes by stripping embedded 4-digit years and whitespace."""
        s = series.fillna("").astype(str).str.strip().str.upper()
        s = s.replace('NAN', '')
        s = s.str.replace(r'\b(20\d{2})\b', '', regex=True)
        s = s.str.replace(r'^(20\d{2})', '', regex=True)
        s = s.str.replace(r'(20\d{2})$', '', regex=True)
        return s.str.strip('_').str.strip('-').str.strip()

    @classmethod
    def _generate_treaty_scheme_id(cls, df: pd.DataFrame) -> pd.Series:
        """
        Generates Treaty Scheme ID ({PRODUCT_ID or COB}-{UY}).
        Prioritizes product_id (e.g. KUC) over COB (e.g. COMMERCIAL CREDIT).
        """
        # Pick product_id first, fallback to COB
        prod_val = df['product_id'].fillna("") if 'product_id' in df.columns else pd.Series("", index=df.index)
        
        # If product_id is empty, try detecting COB
        if prod_val.astype(str).str.strip().eq("").all():
            cob_col = cls._detect_cob_column(df)
            if cob_col:
                prod_val = df[cob_col].fillna("")

        prod_str = prod_val.astype(str).str.strip()
        uy_str = df['uy_final'].fillna("").astype(str).str.strip() if 'uy_final' in df.columns else pd.Series("", index=df.index)

        return np.where(
            (prod_str != "") & (uy_str != ""),
            prod_str + "-" + uy_str,
            prod_str
        )

    @classmethod
    def _apply_cascade_lookup(cls, df_main: pd.DataFrame, df_ref: pd.DataFrame, 
                              main_source_col: str, ref_key_col: str, ref_val_col: str, 
                              target_col_name: str, ref_uy_col: str = None, 
                              ref_pk_col: str = None, use_primary_key: bool = True):
        """
        Multi-tier cascade lookup function:
        1. Explicit/Constructed Treaty Scheme ID match ({CODE}-{UY})
        2. Cleaned Treaty Scheme ID match ({CLEAN_CODE}-{UY})
        3. Direct Code match (Fallback)
        """
        uy_col = 'uy_final'
        
        main_source_series = df_main[main_source_col]
        raw_main_uy = df_main[uy_col].fillna("").astype(str).str.strip().str.upper()
        raw_main_prod = main_source_series.fillna("").astype(str).str.strip().str.upper()
        clean_main_prod = cls._clean_code(main_source_series)

        if target_col_name not in df_main.columns:
            df_main[target_col_name] = np.nan

        # Prepare reference series
        raw_ref_prod = df_ref[ref_key_col].fillna("").astype(str).str.strip().str.upper()
        clean_ref_prod = cls._clean_code(df_ref[ref_key_col])
        ref_values = df_ref[ref_val_col]

        # --- Tier 1 & Tier 2: Treaty Scheme ID Matches ({CODE}-{UY}) ---
        if use_primary_key:
            pk_t1_series = None
            pk_t2_series = None

            if ref_pk_col and ref_pk_col in df_ref.columns:
                pk_t1_series = df_ref[ref_pk_col].fillna("").astype(str).str.strip().str.upper()
                pk_t2_series = cls._clean_code(df_ref[ref_pk_col]) + "-" + (
                    df_ref[ref_uy_col].fillna("").astype(str).str.strip().str.upper()
                    if ref_uy_col and ref_uy_col in df_ref.columns else ""
                )
            elif ref_uy_col and ref_uy_col in df_ref.columns:
                raw_ref_uy = df_ref[ref_uy_col].fillna("").astype(str).str.strip().str.upper()
                pk_t1_series = raw_ref_prod + "-" + raw_ref_uy
                pk_t2_series = clean_ref_prod + "-" + raw_ref_uy

            if pk_t1_series is not None and pk_t2_series is not None:
                map_t1 = dict(zip(pk_t1_series, ref_values))
                map_t2 = dict(zip(pk_t2_series, ref_values))

                key_main_t1 = raw_main_prod + "-" + raw_main_uy
                key_main_t2 = clean_main_prod + "-" + raw_main_uy

                df_main[target_col_name] = df_main[target_col_name].fillna(key_main_t1.map(map_t1))
                df_main[target_col_name] = df_main[target_col_name].fillna(key_main_t2.map(map_t2))

        # --- Tier 3: Direct Code Match (Fallback) ---
        map_clean_prod = dict(zip(clean_ref_prod, ref_values))
        map_raw_prod = dict(zip(raw_ref_prod, ref_values))

        df_main[target_col_name] = df_main[target_col_name].fillna(clean_main_prod.map(map_clean_prod))
        df_main[target_col_name] = df_main[target_col_name].fillna(raw_main_prod.map(map_raw_prod))

    @classmethod
    def process_auto_mapping(cls, main_file, reference_file=None, reference_sheet=None, use_primary_key: bool = True) -> pd.DataFrame:
        df_main = cls._read_file(main_file)

        # 1. Prioritaskan kalkulasi UY dari Tanggal Awal
        inception_col = cls._find_column(df_main, cls.COLUMN_MAPPING['TANGGAL_AWAL'])
        existing_uy_col = cls._find_column(df_main, cls.COLUMN_MAPPING['UY'])

        if inception_col:
            df_main['uy_final'] = cls.calculate_uy_final(df_main[inception_col])
        elif existing_uy_col:
            df_main['uy_final'] = df_main[existing_uy_col].fillna("").astype(str).str.strip()
        else:
            df_main['uy_final'] = ""

        # 2. Deteksi COB dan Product ID pada main dataset
        cob_col = cls._detect_cob_column(df_main)
        product_id_col = cls._detect_product_id_column(df_main)
        is_financial = product_id_col is not None

        main_prod_source = product_id_col if is_financial else cob_col

        # Pre-initialize columns
        if 'product_id' not in df_main.columns:
            df_main['product_id'] = df_main[product_id_col] if product_id_col else np.nan

        if 'cob_treaty' not in df_main.columns:
            df_main['cob_treaty'] = np.nan

        # Initial Treaty Scheme ID build
        df_main['treaty_scheme_id'] = cls._generate_treaty_scheme_id(df_main)

        # 3. Jika Tanpa Reference File
        if reference_file is None:
            if main_prod_source:
                df_main['cob_treaty'] = df_main[main_prod_source]
            df_main.drop(columns=['primary_key'], errors='ignore', inplace=True)
            return df_main

        # 4. Memproses Reference File
        df_ref = cls._read_file(reference_file, sheet_name=reference_sheet)

        ref_uy_col = cls._find_column(df_ref, cls.COLUMN_MAPPING['UY'])
        ref_kode_col = cls._find_column(df_ref, cls.COLUMN_MAPPING['PRODUCT_ID'])
        ref_pk_col = cls._find_column(df_ref, cls.COLUMN_MAPPING['TREATY_SCHEME_ID'])
        ref_cob_col = cls._find_column(df_ref, cls.COLUMN_MAPPING['COB']) or ref_kode_col or df_ref.columns[0]

        # Target COB Treaty column in reference file
        ref_target_col = cls._find_column(df_ref, cls.COLUMN_MAPPING['COB_TREATY'])
        if not ref_target_col:
            for col in df_ref.columns:
                if col not in [ref_uy_col, ref_cob_col, ref_kode_col, ref_pk_col] and any(x in str(col).lower() for x in ['cob', 'treaty', 'group', 'product', 'nama']):
                    ref_target_col = col
                    break
            if not ref_target_col:
                ref_target_col = df_ref.columns[1] if len(df_ref.columns) > 1 else df_ref.columns[0]

        # 5. Lookup Logic Execution
        ref_key_source = ref_kode_col if (is_financial and ref_kode_col) else ref_cob_col

        if main_prod_source and ref_key_source:
            # Step A: Populate/Update PRODUCT_ID using reference 'kode' if available
            if ref_kode_col and ref_kode_col in df_ref.columns:
                cls._apply_cascade_lookup(
                    df_main=df_main,
                    df_ref=df_ref,
                    main_source_col=main_prod_source,
                    ref_key_col=ref_key_source,
                    ref_val_col=ref_kode_col,
                    target_col_name='product_id',
                    ref_uy_col=ref_uy_col,
                    ref_pk_col=ref_pk_col,
                    use_primary_key=use_primary_key
                )

            # Step B: Populate COB_TREATY
            cls._apply_cascade_lookup(
                df_main=df_main,
                df_ref=df_ref,
                main_source_col=main_prod_source,
                ref_key_col=ref_key_source,
                ref_val_col=ref_target_col,
                target_col_name='cob_treaty',
                ref_uy_col=ref_uy_col,
                ref_pk_col=ref_pk_col,
                use_primary_key=use_primary_key
            )

        # Re-generate treaty_scheme_id after lookup to ensure it uses mapped product_id (e.g. KUC-2013)
        df_main['treaty_scheme_id'] = cls._generate_treaty_scheme_id(df_main)

        # Clean up legacy primary_key column if it originated from input data
        df_main.drop(columns=['primary_key'], errors='ignore', inplace=True)

        return df_main