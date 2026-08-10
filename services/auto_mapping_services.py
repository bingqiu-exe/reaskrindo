import re
import io
import numpy as np
import pandas as pd
from django.core.exceptions import ValidationError

class AutoMappingServices:

    COLUMN_MAPPING = {
        'TANGGAL_AWAL': [
            'inception', 'tgl_awal', 'tanggal_awal', 'start_date', 
            'period of ins. awal', 'tanggal awal', 'inception date'
        ],
        'TANGGAL_AKHIR': [
            'expiry', 'tgl_akhir', 'tanggal_akhir', 'end_date', 
            'period of ins. akhir', 'tanggal akhir', 'expiry date'
        ],
        'COB': [
            'product', 'product_name', 'produk', 'nama_produk', 
            'cob', 'class_of_business', 'toc', 'type_of_cover', 
            'line_of_business', 'lob', 'nama produk'
        ],
        'COB_TREATY': [
            'cob_treaty', 'treaty_cob', 'cob reas', 'target_cob', 
            'cob_group', 'group_cob', 'cob_final'
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
            # 1. Baca data awal
            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=target_sheet)
            
            # 2. Jika kolom pertama berupa "Unnamed", cari baris yang berisi kata kunci mapping kita
            if df.columns[0].startswith('Unnamed:'):
                for i, row in df.iterrows():
                    row_str = row.astype(str).str.lower().values
                    # Cek apakah ada kata kunci 'inception' atau alias lainnya di baris ini
                    if any(any(alias in str(val) for alias in cls.COLUMN_MAPPING['TANGGAL_AWAL']) for val in row_str):
                        # Set baris ini sebagai header baru
                        df.columns = df.iloc[i]
                        df = df.iloc[i+1:].reset_index(drop=True)
                        break
            return df

    @classmethod
    def _find_column(cls, df: pd.DataFrame, possible_names: list) -> str:
        """Finds column matching alias exact clean name or substring."""
        # Membersihkan karakter non-breaking space (\xa0) sebelum regex running
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

        raise ValidationError("Could not automatically detect Product or COB column.")

    @classmethod
    def process_auto_mapping(cls, main_file, reference_file=None, reference_sheet=None) -> pd.DataFrame:
        df_main = cls._read_file(main_file)

        # 1. Detect Inception Date and add 'uy_final'
        inception_col = cls._find_column(df_main, cls.COLUMN_MAPPING['TANGGAL_AWAL'])
        if not inception_col:
            raise ValidationError("Could not detect 'Inception' / 'Tanggal Awal' column in main dataset.")

        df_main['uy_final'] = cls.calculate_uy_final(df_main[inception_col])

        # 2. Detect Product / COB source column in main file
        cob_col = cls._detect_cob_column(df_main)

        if 'cob_treaty' not in df_main.columns:
            df_main['cob_treaty'] = np.nan

        # 3. Dynamic Multi-Column Reference Lookup
        if reference_file is not None:
            # reference_sheet is passed here via your dropdown value selection
            df_ref = cls._read_file(reference_file, sheet_name=reference_sheet)

            # Identify which column to map FROM (Source key)
            ref_source_col = cls._find_column(df_ref, cls.COLUMN_MAPPING['COB'])
            if not ref_source_col:
                ref_source_col = df_ref.columns[0] # Fallback to first column if aliases fail

            # Identify which column to map TO (COB Treaty target)
            ref_target_col = cls._find_column(df_ref, cls.COLUMN_MAPPING['COB_TREATY'])
            if not ref_target_col:
                # Fallback: scan for any column that contains 'cob' or 'treaty' in name
                for col in df_ref.columns:
                    if col != ref_source_col and any(x in str(col).lower() for x in ['cob', 'treaty', 'group']):
                        ref_target_col = col
                        break
            if not ref_target_col:
                # Absolute fallback: use the second column if multiple columns exist
                ref_target_col = df_ref.columns[1] if len(df_ref.columns) > 1 else df_ref.columns[0]

            # Build sanitized mapping map (VLOOKUP mechanism)
            df_ref['clean_key'] = df_ref[ref_source_col].astype(str).str.strip().str.lower()
            
            # Remove duplicate reference keys to avoid mapping corruption
            df_ref_clean = df_ref.drop_duplicates(subset=['clean_key'], keep='first')
            mapping_dict = dict(zip(df_ref_clean['clean_key'], df_ref_clean[ref_target_col]))

            # Execute mapping lookup
            clean_main_cob = df_main[cob_col].astype(str).str.strip().str.lower()
            mapped_values = clean_main_cob.map(mapping_dict)

            df_main['cob_treaty'] = df_main['cob_treaty'].fillna(mapped_values)

        return df_main