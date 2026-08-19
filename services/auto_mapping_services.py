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
            'product_id', 'id_product', 'kd_produk', 'kode_produk'
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
        """Detects PRODUCT_ID column (khusus data Finance)."""
        return cls._find_column(df, cls.COLUMN_MAPPING['PRODUCT_ID'])

    @classmethod
    def _clean_code(cls, series: pd.Series) -> pd.Series:
        """Helper to sanitize product codes by stripping embedded 4-digit years and whitespace."""
        s = series.fillna("").astype(str).str.strip().str.lower()
        s = s.replace('nan', '')
        # Remove embedded 4-digit years (e.g., '2024kus' or 'kus2024' -> 'kus')
        s = s.str.replace(r'\b(20\d{2})\b', '', regex=True)
        s = s.str.replace(r'^(20\d{2})', '', regex=True)
        s = s.str.replace(r'(20\d{2})$', '', regex=True)
        return s.str.strip('_').str.strip()

    @classmethod
    def process_auto_mapping(cls, main_file, reference_file=None, reference_sheet=None) -> pd.DataFrame:
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

        uy_col = 'uy_final'

        # 2. Deteksi COB dan Product ID pada main dataset
        cob_col = cls._detect_cob_column(df_main)
        product_id_col = cls._detect_product_id_column(df_main)
        
        is_financial = product_id_col is not None

        if 'cob_treaty' not in df_main.columns:
            df_main['cob_treaty'] = np.nan

        # 3. Jika Tanpa Reference File
        if reference_file is None:
            source_col = product_id_col if is_financial else cob_col
            if source_col:
                df_main['cob_treaty'] = df_main[source_col]
            return df_main

        # 4. Memproses Reference File
        df_ref = cls._read_file(reference_file, sheet_name=reference_sheet)

        ref_uy_col = cls._find_column(df_ref, cls.COLUMN_MAPPING['UY'])
        ref_cob_col = cls._find_column(df_ref, cls.COLUMN_MAPPING['PRODUCT_ID']) or cls._find_column(df_ref, cls.COLUMN_MAPPING['COB'])
        if not ref_cob_col:
            ref_cob_col = df_ref.columns[0]

        ref_target_col = cls._find_column(df_ref, cls.COLUMN_MAPPING['COB_TREATY'])
        if not ref_target_col:
            for col in df_ref.columns:
                if col not in [ref_uy_col, ref_cob_col] and any(x in str(col).lower() for x in ['cob', 'treaty', 'group', 'product', 'nama']):
                    ref_target_col = col
                    break
            if not ref_target_col:
                ref_target_col = df_ref.columns[1] if len(df_ref.columns) > 1 else df_ref.columns[0]

        # Mode Finansial: Multi-tier cascade lookup
        if is_financial:
            main_prod_series = df_main[product_id_col] if product_id_col else df_main[cob_col]
            
            raw_main_uy = df_main[uy_col].fillna("").astype(str).str.strip().str.lower()
            raw_main_prod = main_prod_series.fillna("").astype(str).str.strip().str.lower()
            clean_main_prod = cls._clean_code(main_prod_series)

            # Build reference lookup tables
            if ref_uy_col:
                raw_ref_uy = df_ref[ref_uy_col].fillna("").astype(str).str.strip().str.lower()
                raw_ref_prod = df_ref[ref_cob_col].fillna("").astype(str).str.strip().str.lower()
                clean_ref_prod = cls._clean_code(df_ref[ref_cob_col])

                # Tier 1: Exact UY + Raw Product ID
                df_ref['key_tier1'] = raw_ref_uy + "_" + raw_ref_prod
                map_tier1 = dict(zip(df_ref.drop_duplicates('key_tier1')['key_tier1'], df_ref.drop_duplicates('key_tier1')[ref_target_col]))

                # Tier 2: Exact UY + Cleaned Product ID
                df_ref['key_tier2'] = raw_ref_uy + "_" + clean_ref_prod
                map_tier2 = dict(zip(df_ref.drop_duplicates('key_tier2')['key_tier2'], df_ref.drop_duplicates('key_tier2')[ref_target_col]))

                # Execute Tier 1 & 2 Map
                key_t1 = raw_main_uy + "_" + raw_main_prod
                key_t2 = raw_main_uy + "_" + clean_main_prod
                
                df_main['cob_treaty'] = df_main['cob_treaty'].fillna(key_t1.map(map_tier1))
                df_main['cob_treaty'] = df_main['cob_treaty'].fillna(key_t2.map(map_tier2))

            # Tier 3: Product Code Fallback (Bypasses UY completely)
            df_ref['key_prod_only'] = cls._clean_code(df_ref[ref_cob_col])
            map_prod = dict(zip(df_ref.drop_duplicates('key_prod_only')['key_prod_only'], df_ref.drop_duplicates('key_prod_only')[ref_target_col]))
            
            df_main['cob_treaty'] = df_main['cob_treaty'].fillna(clean_main_prod.map(map_prod))
            df_main['cob_treaty'] = df_main['cob_treaty'].fillna(raw_main_prod.map(map_prod))

        else:
            # Mode Non-Finansial / ASUM: Match purely on COB
            df_ref['clean_key'] = df_ref[ref_cob_col].fillna("").astype(str).str.strip().str.lower()
            main_key_source = df_main[cob_col] if cob_col else df_main.iloc[:, 0]
            clean_main_key = main_key_source.fillna("").astype(str).str.strip().str.lower()

            df_ref_clean = df_ref.drop_duplicates(subset=['clean_key'], keep='first')
            mapping_dict = dict(zip(df_ref_clean['clean_key'], df_ref_clean[ref_target_col]))

            df_main['cob_treaty'] = df_main['cob_treaty'].fillna(clean_main_key.map(mapping_dict))

        return df_main