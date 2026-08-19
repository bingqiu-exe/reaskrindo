import re
import io
import numpy as np
import pandas as pd
from django.core.exceptions import ValidationError

class FinanceServices:
    
    SECURITY_KEYWORDS = [
        'ASURANSI', 'REASURANSI', 'MUNICH', 'PARTNER', 'BRINGIN', 'TUGU',
        'PLN', 'ASIA', 'MEGARE', 'TRINITY', 'ARTHARE', 'APLN', 'ARB',
        'ASKRINDO', 'ODYSSEY', 'BEST', 'ASPEN', 'SAUDI', 'GENERAL',
        'CANOPIUS', 'CHINA', 'VOLANTE', 'QBE', 'TOKIO', 'CHAUCER',
        'PVI', 'HANNOVER',
    ]

    FINANCE_COLUMN_MAPPING = {
        'NO_SERTIFIKAT': [
            'certificate no', 'certificate_no', 'certificate no.', 'no. certificate',
            'no_certificate', 'no certificate', 'no_sertifikat', 'sertifikat_no',
            'no. sertifikat', 'sertifikat no', 'no sertifikat',
        ],
        'NO_KLAIM': ['no_klaim', 'no klaim', 'no. klaim', 'claim_no', 'claim no.', 'claimno'],
        'NAMA DEBITUR': ['insured_name', 'nama tertanggung', 'the insured', 'insured', 'nama_debitur', 'debitur', 'nm_debitur'],
        'COB': ['cob_treaty', 'cob eng', 'cob', 'cob_group', 'class_of_business', 'kode', 'product_name', 'COB_treaty', 'product'],
        'PRODUCT_ID': ['product_id'],
        'TANGGAL_AWAL': ['inception', 'tgl_awal', 'tanggal_awal', 'start_date', 'period of ins. awal'],
        'TANGGAL_AKHIR': ['expiry', 'tgl_akhir', 'tanggal_akhir', 'end_date', 'period of ins. akhir'],
        'DOL_DATE': ['dol_date', 'dol final', 'dol', 'tgl_agenda', 'tanggal_agenda', 'report_date', 'tanggal agenda'],
        'CURRENCY': ['currency', 'curr', 'valuta'],
        'UY_FINAL': ['uy_final', 'uy', 'underwriting_year', 'uw_year', 'uw year', 'uw', 'underwriting_year', 'ay', 'py', 'tahun'],
        'CLAIM_AMOUNT': ['claim_amount', 'claim amount', 'claim_amount_idr', 'gross', 'amt_claim_set', 'gross os klaim', 'amt_outstanding', 'klaim_total (idr)', 'klaim (ori)', 'nil_klaim', 'nilai_klaim', 'total_claim'],
        'QUOTA_SHARE': ['quota_share', 'quota share', 'quota_share_set', 'qs', 'reas_qs', 'pct_qs', 'sor_qs', 'qs share', 'qs_share', 'klaim_qs'],
        'SURPLUS': ['surplus', 'surplus_set', 'sp', 'spl', 'reas_sp', 'pct_sp', 'sor_sp', 'sp share', 'sp_share', 'klaim_sp'],
        'KUPERA': ['kupera'],
        'TENOR': ['tenor', 'tenor_bulan', 'jangka_waktu'],
        'CASHLOSS': ['cashloss', 'cash_loss', 'info3 CC', 'cc', 'cash_call', 'cashcall'],
        'ND': ['nd', 'info2 ND'],
        'KOMISI_QS': ['komisi_qs', 'qs_komisi'],
        'PREMI_QS': ['premi_qs', 'qs_premi'],
        'KLAIM_QS': ['klaim_qs', 'qs_klaim'],
        'KOMISI_SP': ['komisi_sp', 'sp_komisi'],
        'PREMI_SP': ['premi_sp', 'sp_premi'],
        'KLAIM_SP': ['klaim_sp', 'sp_klaim'],
        'RECOVERIES_QS': ['recoveries_qs', 'qs_recoveries', 'qs_recovery', 'recovery_qs'],
        'RECOVERIES_SP': ['recoveries_sp', 'sp_recoveries', 'sp_recovery', 'recovery_sp'],
        'TREATY_SCHEME_ID': ['treaty_scheme_id', 'treaty_scheme', 'scheme_id', 'treaty id']
    }

    REQUIRED_KLAIM_GROUPS = [
        FINANCE_COLUMN_MAPPING['NO_SERTIFIKAT'],
        ['insured', 'debitur', 'tertanggung', 'nm_debitur'],
        ['cob', 'kode', 'product', 'COB_treaty'],
        ['uy', 'uw', 'underwriting', 'tahun'],
        ['claim_amount', 'gross', 'amt', 'outstanding', 'klaim_total', 'klaim'],
    ]

    REQUIRED_PREMI_GROUPS = [
        FINANCE_COLUMN_MAPPING['NO_SERTIFIKAT'],
        ['insured', 'debitur'],
        ['cob', 'kode'],
        ['uy', 'uw', 'underwriting', 'tahun'],
    ]

    FINAL_BLUEPRINT_COLUMNS = [
        'No. Sertifikat', 'No. Klaim', 'Nama Debitur', 'COB', 'Product ID', 
        'Tanggal Awal', 'Tanggal Akhir', 'DOL Date', 'Currency', 'UY Final', 
        'Claim Amount', 'Quota Share', 'Surplus', 'Kupera', 'Long Term', 'Cashloss', 'ND', 'Broker', 'Security', 
        'QS Share', 'SP Share', 'QS Share Amt', 'SP Share Amt',
        'Komisi QS Panel', 'Premi QS Panel', 'Klaim QS Panel', 
        'Komisi SP Panel', 'Premi SP Panel', 'Klaim SP Panel', 
        'Recoveries QS Panel', 'Recoveries SP Panel'
    ]

    @classmethod
    def _read_file(cls, uploaded_file, required_terms: list = None) -> pd.DataFrame:
        filename = uploaded_file.name.lower()
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        
        def read_fn(header_row):
            if filename.endswith('.csv'):
                encodings = ['utf-8-sig', 'cp1252', 'latin1']
                separators = [',', ';', '\t']
                for enc in encodings:
                    for sep in separators:
                        try:
                            df = pd.read_csv(
                                io.BytesIO(file_bytes), 
                                header=header_row, 
                                encoding=enc, 
                                sep=sep, 
                                low_memory=False
                            )
                            if len(df.columns) > 1:
                                return df
                        except Exception:
                            continue
                return pd.read_csv(io.BytesIO(file_bytes), header=header_row, encoding='latin1', low_memory=False)
            elif filename.endswith(('.xls', '.xlsx')):
                return pd.read_excel(io.BytesIO(file_bytes), header=header_row)
            else:
                raise ValidationError("Unsupported file format. Please upload CSV or Excel.")

        MAX_HEADER_SCAN = 5 if required_terms else 2
        
        for header_idx in range(MAX_HEADER_SCAN):
            try:
                df = read_fn(header_idx)
                if not required_terms:
                    unnamed_count = sum(1 for c in df.columns if 'unnamed' in str(c).lower())
                    if unnamed_count < len(df.columns) / 2:
                        return df
                    continue

                cols_clean = [re.sub(r'[\s_\-/]+', '', str(c)).strip().lower() for c in df.columns]
                missing_groups = []
                
                for group in required_terms:
                    aliases = group if isinstance(group, list) else [group]
                    clean_aliases = [re.sub(r'[\s_\-/]+', '', a).strip().lower() for a in aliases]
                    
                    match_found = any(
                        any(alias in col or col in alias for col in cols_clean if col)
                        for alias in clean_aliases if alias
                    )
                    if not match_found:
                        missing_groups.append("/".join(aliases))
                        break
                    
                if not missing_groups:
                    return df
            except Exception:
                continue

        return read_fn(0)

    @classmethod
    def _get_column_value(cls, df: pd.DataFrame, possible_names: list, default="") -> pd.Series:
        normalized_cols = {re.sub(r'[\s_\-/]+', '', str(col)).strip().lower(): col for col in df.columns}
        
        for alias in possible_names:
            alias_clean = re.sub(r'[\s_\-/]+', '', alias).strip().lower()
            if alias_clean in normalized_cols:
                return df[normalized_cols[alias_clean]]

        for alias in possible_names:
            alias_clean = re.sub(r'[\s_\-/]+', '', alias).strip().lower()
            if not alias_clean:
                continue
            for col_clean, original_col in normalized_cols.items():
                if alias_clean in col_clean or (len(col_clean) > 2 and col_clean in alias_clean):
                    return df[original_col]
                
        return pd.Series(default, index=df.index)

    @classmethod
    def _get_numeric_column(cls, df: pd.DataFrame, possible_names: list, default=0.0) -> pd.Series:
        s = cls._get_column_value(df, possible_names, default=default)
        if s.empty:
            return pd.Series(default, index=df.index)
        
        s_str = s.astype(str).str.strip().str.replace('%', '', regex=False)
        s_str = s_str.str.replace(r'[\s\n\r]', '', regex=True)
        
        numeric_series = pd.to_numeric(s_str, errors='coerce')
        
        fallback_mask = numeric_series.isna() & ~s_str.isin(['', 'nan', 'none', 'null', '-'])
        if fallback_mask.any():
            fallback_cleaned = s_str[fallback_mask].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            numeric_series[fallback_mask] = pd.to_numeric(fallback_cleaned, errors='coerce')

        return numeric_series.fillna(default).astype(float)

    @classmethod
    def _normalize_share_decimal(cls, series: pd.Series) -> pd.Series:
        return np.where(series > 1.0, series / 100.0, series).round(6)

    @classmethod
    def _normalize_key_string(cls, series: pd.Series) -> pd.Series:
        return (
            series.astype(str)
            .str.replace(r'\s*\([Ll][Tt]\)\s*', '', regex=True)
            .str.upper()
            .str.replace(r'[\s\-_/]+', '', regex=True)
            .str.strip()
        )

    @classmethod
    def _extract_main_primary_key(cls, df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
        raw_key = cls._get_column_value(df, cls.FINANCE_COLUMN_MAPPING['TREATY_SCHEME_ID']).astype(str).str.strip()
        calculated_key = cls._normalize_key_string(raw_key)
        raw_key_normalized = raw_key.str.upper().str.replace(r'[\s\-_/]+', '', regex=True).str.strip()
        
        extracted_prefix = raw_key.str.replace(r'\b(19|20)\d{2}\b|\d{2,4}$', '', regex=True)
        extracted_prefix_key = cls._normalize_key_string(extracted_prefix)
        
        cob_fallback = cls._normalize_key_string(cls._get_column_value(df, cls.FINANCE_COLUMN_MAPPING['COB']))
        extracted_prefix_key = np.where(
            extracted_prefix_key.isin(['', 'NAN', 'NONE', 'NULL']), 
            cob_fallback, 
            extracted_prefix_key
        )
        extracted_prefix_key = pd.Series(extracted_prefix_key, index=df.index)

        return calculated_key, raw_key_normalized, extracted_prefix_key

    @classmethod
    def _build_reference_primary_key(cls, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        node_series = cls._get_column_value(df, ['kode', 'cob', 'product']).astype(str).str.strip()
        uy_series = cls._get_column_value(df, ['uy', 'uw', 'underwriting_year', 'tahun']).astype(str).str.strip()
        
        combined = node_series + '-' + uy_series
        calculated_key = cls._normalize_key_string(combined)
        raw_key_normalized = combined.str.upper().str.replace(r'[\s\-_/]+', '', regex=True).str.strip()
        return calculated_key, raw_key_normalized

    @classmethod
    def _merge_with_treaty(cls, df_main_clean: pd.DataFrame, df_treaty: pd.DataFrame) -> pd.DataFrame:
        treaty_rumus, raw_treaty_rumus = cls._build_reference_primary_key(df_treaty)

        treaty_uy_raw = cls._get_column_value(df_treaty, ['uy', 'uw', 'underwriting_year', 'tahun']).astype(str).str.strip()
        treaty_uy = cls._normalize_key_string(treaty_uy_raw)

        broker_raw = cls._get_column_value(df_treaty, ['broker_used', 'broker']).astype(str)
        security_raw = cls._get_column_value(df_treaty, ['security_used', 'security']).astype(str)
        
        komisi_qs = cls._normalize_share_decimal(cls._get_numeric_column(df_treaty, ['komisi_qs_per_panel', 'komisi_qs']))
        komisi_sp = cls._normalize_share_decimal(cls._get_numeric_column(df_treaty, ['komisi_sp_per_panel', 'komisi_sp']))

        share_qs_panel = cls._get_numeric_column(df_treaty, ['share_qs_panel_of_share_reas', 'share_qs'])
        share_sp_panel = cls._get_numeric_column(df_treaty, ['share_sp_panel_of_share_reas', 'share_sp'])

        kw_pattern = '|'.join(cls.SECURITY_KEYWORDS)
        split_regex_str = rf',\s*(?=(?:{kw_pattern})\b)'
        compiled_regex = re.compile(split_regex_str, flags=re.IGNORECASE)

        df_exp_prep = pd.DataFrame({
            'rumus_key': treaty_rumus,
            'raw_rumus_key': raw_treaty_rumus,
            'treaty_uy': treaty_uy,
            'broker_used': broker_raw.str.split(compiled_regex),
            'security_used': security_raw.str.split(compiled_regex),
            'komisi_qs_per_panel': komisi_qs,
            'komisi_sp_per_panel': komisi_sp,
            'share_qs_panel_of_share_reas': share_qs_panel,
            'share_sp_panel_of_share_reas': share_sp_panel
        })

        df_expanded = df_exp_prep.explode(['broker_used', 'security_used'])
        df_expanded['broker_used'] = df_expanded['broker_used'].str.strip().fillna('')
        df_expanded['security_used'] = df_expanded['security_used'].str.strip().fillna('')
        df_expanded = df_expanded[(df_expanded['broker_used'] != '') | (df_expanded['security_used'] != '')]

        df_distinct_treaty = df_expanded.drop_duplicates(
            subset=['rumus_key', 'treaty_uy', 'broker_used', 'security_used']
        ).copy()

        for col, new_col in [('share_qs_panel_of_share_reas', 'norm_share_qs'), 
                             ('share_sp_panel_of_share_reas', 'norm_share_sp')]:
            sum_shares = df_distinct_treaty.groupby(['rumus_key', 'treaty_uy'])[col].transform('sum')
            df_distinct_treaty[new_col] = np.where(
                sum_shares > 0, 
                df_distinct_treaty[col] / sum_shares, 
                df_distinct_treaty[col]
            )
            df_distinct_treaty[col] = df_distinct_treaty[new_col]

        df_cleaned_treaty = df_distinct_treaty.drop(columns=['norm_share_qs', 'norm_share_sp'])

        merged_primary = pd.merge(
            df_main_clean, df_cleaned_treaty, 
            left_on=['calculated_rumus', 'uy_clean'], 
            right_on=['rumus_key', 'treaty_uy'], 
            how='inner'
        )
        
        matched_orig_indices = set(merged_primary['_orig_idx'])
        unmatched_step1 = df_main_clean[~df_main_clean['_orig_idx'].isin(matched_orig_indices)].copy()
        
        unmatched_step1['dynamic_target_key'] = unmatched_step1['prefix_rumus'] + unmatched_step1['uy_clean']
        
        merged_dynamic_prefix = pd.merge(
            unmatched_step1, df_cleaned_treaty,
            left_on=['dynamic_target_key', 'uy_clean'],
            right_on=['rumus_key', 'treaty_uy'],
            how='inner'
        ).drop(columns=['dynamic_target_key'])

        matched_orig_indices = matched_orig_indices.union(set(merged_dynamic_prefix['_orig_idx']))
        unmatched_step2 = df_main_clean[~df_main_clean['_orig_idx'].isin(matched_orig_indices)]
        
        merged_fallback = pd.merge(
            unmatched_step2, df_cleaned_treaty, 
            left_on=['fallback_rumus', 'uy_clean'], 
            right_on=['raw_rumus_key', 'treaty_uy'], 
            how='inner'
        )

        matched_orig_indices = matched_orig_indices.union(set(merged_fallback['_orig_idx']))
        unmatched_all = df_main_clean[~df_main_clean['_orig_idx'].isin(matched_orig_indices)].copy()

        unmatched_all['rumus_key'] = np.nan
        unmatched_all['raw_rumus_key'] = np.nan
        unmatched_all['treaty_uy'] = np.nan
        unmatched_all['broker_used'] = np.nan
        unmatched_all['security_used'] = np.nan
        unmatched_all['komisi_qs_per_panel'] = 0.0
        unmatched_all['komisi_sp_per_panel'] = 0.0
        unmatched_all['share_qs_panel_of_share_reas'] = 1.0
        unmatched_all['share_sp_panel_of_share_reas'] = 1.0

        df_joined = pd.concat([merged_primary, merged_dynamic_prefix, merged_fallback, unmatched_all], ignore_index=True)
        return df_joined.sort_values(by=['_orig_idx', 'security_used'], na_position='last').reset_index(drop=True)

    @classmethod
    def _build_structural_dataframe(cls, df_source) -> pd.DataFrame:
        uy_raw = cls._get_column_value(df_source, cls.FINANCE_COLUMN_MAPPING['UY_FINAL']).astype(str).str.strip().fillna('')
        uy_clean_series = cls._normalize_key_string(uy_raw)

        # 1. Fetch PRODUCT_ID and normalize string format (uppercase & stripped)
        cob_series = (
            cls._get_column_value(df_source, cls.FINANCE_COLUMN_MAPPING['COB'])
            .astype(str)
            .str.strip()
            .str.upper()
        )
        
        # 2. Extract numeric tenor values
        tenor_series = cls._get_numeric_column(df_source, cls.FINANCE_COLUMN_MAPPING['TENOR'])

        # 3. Build conditional evaluation masks:
        # Rule 1: PRODUCT_ID == 'KUS', tenor > 180, and uy == '2023'
        # Rule 2: PRODUCT_ID == 'KUK', tenor > 60, and uy == '2023'
        cond_kus_long = (cob_series == 'CONSUMPTIVE CREDIT') & (tenor_series > 180) & (uy_clean_series == '2023')
        cond_kuk_long = (cob_series == 'PRODUCTIVE CREDIT') & (tenor_series > 60) & (uy_clean_series == '2023')

        # 4. Vectorized assignment ('Long' if either condition is met, otherwise 'No')
        long_term_computed = np.where(cond_kus_long | cond_kuk_long, 'Long', 'No')

        # Helper lambda to treat NaN values as real empty strings instead of stringified versions like 'nan'
        clean_str = lambda col_name: cls._get_column_value(df_source, cls.FINANCE_COLUMN_MAPPING[col_name]).astype(str).str.strip().replace(['nan', 'NaN', 'None', 'nat', 'NaT'], '')

        return pd.DataFrame({
            'NO_SERTIFIKAT': clean_str('NO_SERTIFIKAT'),
            'NAMA DEBITUR': clean_str('NAMA DEBITUR'),
            'COB': clean_str('COB'),
            'PRODUCT_ID': clean_str('PRODUCT_ID'),
            'TANGGAL_AWAL': clean_str('TANGGAL_AWAL'),
            'TANGGAL_AKHIR': clean_str('TANGGAL_AKHIR'),
            'CURRENCY': clean_str('CURRENCY'),
            'UW YEAR': uy_raw,
            'uy_clean': uy_clean_series,
            'QS': cls._normalize_share_decimal(cls._get_numeric_column(df_source, cls.FINANCE_COLUMN_MAPPING['QUOTA_SHARE'])),
            'SPL': cls._normalize_share_decimal(cls._get_numeric_column(df_source, cls.FINANCE_COLUMN_MAPPING['SURPLUS'])),
            'KUPERA': clean_str('KUPERA'),
            'LONG_TERM': long_term_computed,
            'CASHLOSS': clean_str('CASHLOSS'),
            'ND': clean_str('ND'),
            'premi_qs': cls._get_numeric_column(df_source, cls.FINANCE_COLUMN_MAPPING['PREMI_QS']),
            'klaim_qs': cls._get_numeric_column(df_source, cls.FINANCE_COLUMN_MAPPING['KLAIM_QS']),
            'komisi_qs': cls._get_numeric_column(df_source, cls.FINANCE_COLUMN_MAPPING['KOMISI_QS']),
            'premi_sp': cls._get_numeric_column(df_source, cls.FINANCE_COLUMN_MAPPING['PREMI_SP']),
            'klaim_sp': cls._get_numeric_column(df_source, cls.FINANCE_COLUMN_MAPPING['KLAIM_SP']),
            'komisi_sp': cls._get_numeric_column(df_source, cls.FINANCE_COLUMN_MAPPING['KOMISI_SP']),
            'recoveries_qs': cls._get_numeric_column(df_source, cls.FINANCE_COLUMN_MAPPING['RECOVERIES_QS']),
            'recoveries_sp': cls._get_numeric_column(df_source, cls.FINANCE_COLUMN_MAPPING['RECOVERIES_SP']),
        })

    @classmethod
    def _finalize_blueprint_output(cls, df: pd.DataFrame) -> pd.DataFrame:
        qs_mult = df['share_qs_panel_of_share_reas'].fillna(0.0)
        sp_mult = df['share_sp_panel_of_share_reas'].fillna(0.0)

        df_out = pd.DataFrame(index=df.index)
        df_out['No. Sertifikat'] = df['NO_SERTIFIKAT']
        df_out['No. Klaim'] = df['NO_KLAIM']
        df_out['Nama Debitur'] = df['NAMA DEBITUR']
        df_out['COB'] = df['COB']
        df_out['Product ID'] = df['PRODUCT_ID']
        df_out['Tanggal Awal'] = df['TANGGAL_AWAL']
        df_out['Tanggal Akhir'] = df['TANGGAL_AKHIR']
        df_out['DOL Date'] = df['DOL_DATE']
        df_out['Currency'] = df['CURRENCY']
        df_out['UY Final'] = df['UW YEAR']
        df_out['Claim Amount'] = df['CLAIM_AMOUNT']
        df_out['Quota Share'] = df['QS']
        df_out['Surplus'] = df['SPL']
        df_out['Kupera'] = df['KUPERA']
        df_out['Long Term'] = df['LONG_TERM']
        df_out['Cashloss'] = df['CASHLOSS']
        df_out['ND'] = df['ND']
        df_out['Broker'] = df['broker_used']
        df_out['Security'] = df['security_used']
        
        df_out['QS Share'] = qs_mult.round(6)
        df_out['SP Share'] = sp_mult.round(6)
        df_out['QS Share Amt'] = (df['CLAIM_AMOUNT'] * df['QS'] * qs_mult).round(2)
        df_out['SP Share Amt'] = (df['CLAIM_AMOUNT'] * df['SPL'] * sp_mult).round(2)
        
        df_out['Komisi QS Panel'] = (df['komisi_qs'] * qs_mult).round(2)
        df_out['Premi QS Panel'] = (df['premi_qs'] * qs_mult).round(2)
        df_out['Klaim QS Panel'] = (df['klaim_qs'] * qs_mult).round(2)
        
        df_out['Komisi SP Panel'] = (df['komisi_sp'] * sp_mult).round(2)
        df_out['Premi SP Panel'] = (df['premi_sp'] * sp_mult).round(2)
        df_out['Klaim SP Panel'] = (df['klaim_sp'] * sp_mult).round(2)
        
        df_out['Recoveries QS Panel'] = (df['recoveries_qs'] * qs_mult).round(2)
        df_out['Recoveries SP Panel'] = (df['recoveries_sp'] * sp_mult).round(2)
        
        return df_out[cls.FINAL_BLUEPRINT_COLUMNS]

    @classmethod
    def process_finance_allocation_premi(cls, main_file, reference_file) -> pd.DataFrame:
        df_claim = cls._read_file(main_file, required_terms=cls.REQUIRED_PREMI_GROUPS)
        df_treaty = cls._read_file(reference_file)

        df_clean = cls._build_structural_dataframe(df_claim)
        df_clean['NO_KLAIM'] = ""
        df_clean['DOL_DATE'] = ""
        df_clean['CLAIM_AMOUNT'] = cls._get_numeric_column(df_claim, cls.FINANCE_COLUMN_MAPPING['CLAIM_AMOUNT'])

        calculated_rumus, fallback_rumus, prefix_rumus = cls._extract_main_primary_key(df_claim)
        df_clean['calculated_rumus'] = calculated_rumus
        df_clean['fallback_rumus'] = fallback_rumus
        df_clean['prefix_rumus'] = prefix_rumus
        df_clean['_orig_idx'] = np.arange(len(df_claim))

        df_joined = cls._merge_with_treaty(df_clean, df_treaty)
        return cls._finalize_blueprint_output(df_joined)

    @classmethod
    def process_finance_allocation_claim(cls, main_file, reference_file) -> pd.DataFrame:
        df_claim = cls._read_file(main_file, required_terms=cls.REQUIRED_KLAIM_GROUPS)
        df_treaty = cls._read_file(reference_file)

        df_clean = cls._build_structural_dataframe(df_claim)
        no_sertifikat = df_clean['NO_SERTIFIKAT']
        no_klaim = cls._get_column_value(df_claim, cls.FINANCE_COLUMN_MAPPING['NO_KLAIM']).astype(str).str.strip().fillna('')
        
        df_clean['NO_KLAIM'] = np.where((no_klaim == '') | (no_klaim == 'nan'), no_sertifikat, no_klaim)
        df_clean['DOL_DATE'] = cls._get_column_value(df_claim, cls.FINANCE_COLUMN_MAPPING['DOL_DATE']).astype(str).str.strip().fillna('')
        df_clean['CLAIM_AMOUNT'] = cls._get_numeric_column(df_claim, cls.FINANCE_COLUMN_MAPPING['CLAIM_AMOUNT'])

        calculated_rumus, fallback_rumus, prefix_rumus = cls._extract_main_primary_key(df_claim)
        df_clean['calculated_rumus'] = calculated_rumus
        df_clean['fallback_rumus'] = fallback_rumus
        df_clean['prefix_rumus'] = prefix_rumus
        df_clean['_orig_idx'] = np.arange(len(df_claim))

        df_joined = cls._merge_with_treaty(df_clean, df_treaty)
        return cls._finalize_blueprint_output(df_joined)