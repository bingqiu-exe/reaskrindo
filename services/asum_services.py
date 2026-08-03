import re
import io
import numpy as np
import pandas as pd
from django.core.exceptions import ValidationError

class AsumServices:
    
    SECURITY_KEYWORDS = [
        'ASURANSI', 'REASURANSI', 'MUNICH', 'PARTNER', 'BRINGIN', 'TUGU', 'PLN', 
        'ASIA', 'MEGARE', 'TRINITY', 'ARTHARE', 'APLN', 'ARB', 'ASKRINDO', 
        'ODYSSEY', 'BEST', 'ASPEN', 'SAUDI', 'GENERAL', 'CANOPIUS', 'CHINA', 
        'VOLANTE', 'QBE', 'TOKIO', 'CHAUCER', 'PVI', 'HANNOVER'
    ]

    COLUMN_MAPPING_KLAIM = {
        'POLICYREF_NO': ['policyref no', 'policyref_no', 'policy_refno', 'policy_ref_no', 'ref_no', 'no_ref', 'policy ref no', 'no. reg', 'no. registrasi', 'no_reg', 'reg_no', 'reg no.', 'nomor registrasi', 'nomor_registrasi'],
        'POLICY_NO': ['policy_no', 'policy_number', 'policy number', 'policy', 'polis', 'nopolis', 'claimno'],
        'INSURED_NAME': ['insured_name', 'nama tertanggung', 'the insured', 'insured', 'nama_debitur', 'debitur'],
        'COB_TREATY': ['cob_treaty', 'cob eng', 'cob', 'cob_group', 'class_of_business', 'kode', 'product_name'],
        'INCEPTION': ['inception', 'tgl_awal', 'tanggal_awal', 'start_date', 'period of ins. awal'],
        'EXPIRY': ['expiry', 'tgl_akhir', 'tanggal_akhir', 'end_date', 'period of ins. akhir'],
        'DOL_DATE': ['dol_date', 'dol final', 'dol', 'tgl_agenda', 'tanggal_agenda', 'report_date'],
        'CURRENCY': ['currency', 'curr', 'valuta'],
        'UY_FINAL': ['uy_final', 'uy', 'uw_year', 'uw year', 'uw', 'underwriting_year', 'ay', 'py'],
        'CLAIM_AMOUNT': ['claim_amount', 'claim amount', 'claim_amount_idr', 'gross', 'amt_claim_set', 'gross os klaim', 'amt_outstanding'],
        'QUOTA_SHARE': ['quota_share', 'quota share', 'quota_share_set', 'qs', 'reas_qs', 'pct_qs', 'sor_qs', 'qs share', 'qs_share'],
        'SURPLUS': ['surplus', 'surplus_set', 'sp', 'spl', 'reas_sp', 'pct_sp', 'sor_sp', 'sp share', 'sp_share']
    }

    # FIX 1: Define specific core required groups for Claim validation (don't require all 11 columns)
    REQUIRED_KLAIM_GROUPS = [
        ['policy', 'polis', 'nopolis', 'claimno'],
        ['insured', 'debitur', 'tertanggung'],
        ['cob', 'kode', 'product'],
        ['claim_amount', 'gross', 'amt', 'outstanding']
    ]

    REQUIRED_PREMI_GROUPS = [
        ['policy', 'polis'],
        ['insured', 'debitur'],
        ['cob', 'kode'],
        ['inception', 'awal', 'start', 'tgl_awal'],
        ['expiry', 'akhir', 'end', 'tgl_akhir'],
        ['currency', 'curr', 'valuta'],
        ['uy', 'uw', 'underwriting'],
        ['tsi', 'claim_amount', 'claim amount'],
        ['quota share', 'qs'],
        ['surplus', 'sp', 'spl']
    ]

    @classmethod
    def _read_file(cls, uploaded_file, required_terms: list = None) -> pd.DataFrame:
        filename = uploaded_file.name.lower()
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        
        def read_fn(header_row):
            if filename.endswith('.csv'):
                encodings = ['utf-8-sig', 'cp1252', 'latin1', 'iso-8859-1']
                separators = [None, ';', ',', '\t']
                
                for enc in encodings:
                    for sep in separators:
                        try:
                            df = pd.read_csv(
                                io.BytesIO(file_bytes), 
                                header=header_row, 
                                encoding=enc, 
                                engine='python', 
                                sep=sep
                            )
                            if len(df.columns) > 1 or sep == separators[-1]:
                                return df
                        except Exception:
                            continue

                return pd.read_csv(io.BytesIO(file_bytes), header=header_row, encoding='latin1', sep=None, engine='python')
                
            elif filename.endswith(('.xls', '.xlsx')):
                return pd.read_excel(io.BytesIO(file_bytes), header=header_row)
            else:
                raise ValidationError("Unsupported file format. Please upload CSV or Excel (.xlsx).")

        # Search depth: Scan up to 25 rows to accommodate title headers
        MAX_HEADER_SCAN = 25

        # If no required terms provided (e.g., reference file), scan for the first non-empty header row
        if not required_terms:
            for idx in range(MAX_HEADER_SCAN):
                try:
                    df = read_fn(idx)
                    unnamed_count = sum(1 for c in df.columns if 'unnamed' in str(c).lower())
                    if unnamed_count < len(df.columns) / 2:
                        return df
                except Exception:
                    continue
            return read_fn(0)

        # Required terms loop logic with flexible substring matching
        failed_attempts = []
        for header_idx in range(MAX_HEADER_SCAN):
            try:
                df = read_fn(header_idx)
                cols_clean = [re.sub(r'[\s_\-/]+', '', str(c)).strip().lower() for c in df.columns]

                missing_groups = []
                for group in required_terms:
                    aliases = group if isinstance(group, list) else [group]
                    clean_aliases = [re.sub(r'[\s_\-/]+', '', a).strip().lower() for a in aliases]
                    
                    # FIX 2: Check if alias exists as a substring or exact match in any cleaned column header
                    match_found = any(
                        alias in col or col in alias 
                        for col in cols_clean 
                        for alias in clean_aliases 
                        if col and alias
                    )
                    
                    if not match_found:
                        missing_groups.append("/".join(aliases))
                    
                if not missing_groups:
                    return df
                else:
                    failed_attempts.append(f"Row {header_idx} missing: {', '.join(missing_groups[:2])}")
                    
            except Exception as e:
                failed_attempts.append(f"Row {header_idx} error: {str(e)}")
                continue

        debug_msg = " | ".join(failed_attempts[:3])
        raise ValidationError(
            f"Failed to detect required header columns in '{uploaded_file.name}'. Debug Info: {debug_msg}"
        )

    @classmethod
    def _get_column_value(cls, df: pd.DataFrame, possible_names: list, default="") -> pd.Series:
        normalized_cols = {re.sub(r'[\s_\-/]+', '', str(col)).strip().lower(): col for col in df.columns}
        
        # 1. Exact match pass
        for alias in possible_names:
            alias_clean = re.sub(r'[\s_\-/]+', '', alias).strip().lower()
            if alias_clean in normalized_cols:
                return df[normalized_cols[alias_clean]]

        # 2. Bi-directional substring pass (checks if alias in col OR col in alias)
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
        if isinstance(s, (int, float)):
            return pd.Series(default, index=df.index)

        def clean_val(val):
            if pd.isna(val) or val is None:
                return default
            val_str = str(val).strip().replace('%', '') # Strip % signs
            if val_str in ['', 'nan', 'None', 'null', '-']:
                return default

            try:
                return float(val_str)
            except ValueError:
                pass

            # Handle European format: 1.000,50 -> 1000.50
            cleaned = val_str.replace('.', '').replace(',', '.')
            try:
                return float(cleaned)
            except ValueError:
                return default

        return s.apply(clean_val).astype(float)

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
    def _extract_or_build_primary_key(cls, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        possible_pk_cols = ['rumus', 'rumus_key', 'pk', 'primary_key', 'unique_code']
        
        existing_pk_col = None
        for col in df.columns:
            cleaned_col_name = str(col).strip().lower().replace(' ', '').replace('_', '')
            if cleaned_col_name in [p.replace('-', '').replace('_', '').replace('/', '') for p in possible_pk_cols]:
                existing_pk_col = col
                break

        if existing_pk_col is not None:
            raw_key = df[existing_pk_col].astype(str)
            calculated_key = cls._normalize_key_string(raw_key)
            raw_key_normalized = (
                raw_key.astype(str)
                .str.upper()
                .str.replace(r'[\s\-_/]+', '', regex=True)
                .str.strip()
            )
            return calculated_key, raw_key_normalized

        cob_series = cls._get_column_value(df, ['cob_treaty', 'cob', 'class_of_business', 'kode', 'product_name']).astype(str).str.strip()
        uy_series = cls._get_column_value(df, ['uy_final', 'uy', 'underwriting_year', 'uw_year', 'uw year']).astype(str).str.strip()

        calculated_key = cls._normalize_key_string(uy_series + cob_series)
        uy_4digits = uy_series.str.slice(0, 4)
        
        raw_cob = (
            cob_series.astype(str)
            .str.upper()
            .str.replace(r'[\s\-_/]+', '', regex=True)
            .str.strip()
        )
        fallback_key = uy_4digits + raw_cob

        return calculated_key, fallback_key

    @classmethod
    def _merge_with_treaty(cls, df_main_clean: pd.DataFrame, df_treaty: pd.DataFrame) -> pd.DataFrame:
        treaty_rumus, raw_treaty_rumus = cls._extract_or_build_primary_key(df_treaty)

        broker_raw = cls._get_column_value(df_treaty, ['broker_used', 'broker']).astype(str)
        security_raw = cls._get_column_value(df_treaty, ['security_used', 'security']).astype(str)
        
        komisi_qs = cls._get_numeric_column(df_treaty, ['komisi_qs_per_panel', 'komisi_qs'])
        komisi_sp = cls._get_numeric_column(df_treaty, ['komisi_sp_per_panel', 'komisi_sp'])
        share_qs_panel = cls._get_numeric_column(df_treaty, ['share_qs_panel_of_share_reas', 'share_qs_per_panel_of_100_pct', 'share_qs', 'broker_qs_share'])
        share_sp_panel = cls._get_numeric_column(df_treaty, ['share_sp_panel_of_share_reas', 'broker_sp_share', 'share_sp'])

        kw_pattern = '|'.join(cls.SECURITY_KEYWORDS)
        split_regex = rf',\s*(?=(?:{kw_pattern})\b)'

        expanded_rows = []
        for idx in range(len(df_treaty)):
            r_key = treaty_rumus.iloc[idx]
            raw_r_key = raw_treaty_rumus.iloc[idx]
            
            b_list = [b.strip() for b in re.split(split_regex, broker_raw.iloc[idx], flags=re.IGNORECASE) if b.strip()]
            s_list = [s.strip() for s in re.split(split_regex, security_raw.iloc[idx], flags=re.IGNORECASE) if s.strip()]

            max_len = max(len(b_list), len(s_list), 1)
            for i in range(max_len):
                b_val = b_list[i] if i < len(b_list) else (b_list[0] if b_list else '')
                s_val = s_list[i] if i < len(s_list) else (s_list[0] if s_list else '')
                expanded_rows.append({
                    'rumus_key': r_key,
                    'raw_rumus_key': raw_r_key,
                    'broker_used': b_val,
                    'security_used': s_val,
                    'komisi_qs_per_panel': komisi_qs.iloc[idx],
                    'komisi_sp_per_panel': komisi_sp.iloc[idx],
                    'share_qs_panel_of_share_reas': share_qs_panel.iloc[idx],
                    'share_sp_panel_of_share_reas': share_sp_panel.iloc[idx]
                })

        df_expanded = pd.DataFrame(expanded_rows)

        df_cleaned_treaty = df_expanded.groupby(['rumus_key', 'raw_rumus_key', 'broker_used', 'security_used'], as_index=False).agg({
            'komisi_qs_per_panel': 'max',
            'komisi_sp_per_panel': 'max',
            'share_qs_panel_of_share_reas': 'max',
            'share_sp_panel_of_share_reas': 'max'
        })

        known_rumus_keys = set(df_cleaned_treaty['rumus_key'].unique())

        merged_primary = pd.merge(
            df_main_clean,
            df_cleaned_treaty,
            left_on='calculated_rumus',
            right_on='rumus_key',
            how='inner'
        )

        unmatched_claims = df_main_clean[~df_main_clean['calculated_rumus'].isin(known_rumus_keys)]
        
        merged_fallback = pd.merge(
            unmatched_claims,
            df_cleaned_treaty,
            left_on='fallback_rumus',
            right_on='raw_rumus_key',
            how='inner'
        )

        matched_orig_indices = set(merged_primary['_orig_idx']).union(set(merged_fallback['_orig_idx']))
        unmatched_all = df_main_clean[~df_main_clean['_orig_idx'].isin(matched_orig_indices)].copy()

        unmatched_all['rumus_key'] = np.nan
        unmatched_all['raw_rumus_key'] = np.nan
        unmatched_all['broker_used'] = np.nan
        unmatched_all['security_used'] = np.nan
        # In _merge_with_treaty:
        unmatched_all['komisi_qs_per_panel'] = 0.0
        unmatched_all['komisi_sp_per_panel'] = 0.0

        # Fill with 1.0 (or NaN) instead of 0.0 so multiplication preserves original QS/SPL
        unmatched_all['share_qs_panel_of_share_reas'] = 1.0
        unmatched_all['share_sp_panel_of_share_reas'] = 1.0

        df_joined = pd.concat([merged_primary, merged_fallback, unmatched_all], ignore_index=True)
        df_joined = df_joined.sort_values(by=['_orig_idx', 'security_used'], na_position='last').reset_index(drop=True)

        return df_joined

    # PREMI ALLOCATION
    @classmethod
    def process_asum_allocation_premi(cls, main_file, reference_file) -> pd.DataFrame:
        df_claim = cls._read_file(main_file, required_terms=cls.REQUIRED_PREMI_GROUPS)
        df_treaty = cls._read_file(reference_file)

        no_polis = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['POLICY_NO']).astype(str).str.strip()
        no_reg = cls._get_column_value(df_claim, ['no_reg', 'registration_id', 'preliminary_id', 'claimno']).astype(str).str.strip()
        insured_name = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['INSURED_NAME']).astype(str).str.strip()
        cob_treaty = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['COB_TREATY']).astype(str).str.strip()
        inception = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['INCEPTION']).astype(str).str.strip()
        expiry = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['EXPIRY']).astype(str).str.strip()
        dol_date = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['DOL_DATE']).astype(str).str.strip()
        currency = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['CURRENCY']).astype(str).str.strip()
        uy_final = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['UY_FINAL']).astype(str).str.strip()
        
        claim_amount = cls._get_numeric_column(df_claim, cls.COLUMN_MAPPING_KLAIM['CLAIM_AMOUNT'])
        quota_share = cls._get_numeric_column(df_claim, cls.COLUMN_MAPPING_KLAIM['QUOTA_SHARE'])
        surplus = cls._get_numeric_column(df_claim, cls.COLUMN_MAPPING_KLAIM['SURPLUS'])

        calculated_rumus, fallback_rumus = cls._extract_or_build_primary_key(df_claim)

        df_clean = pd.DataFrame({
            'POLICY NUMBER': no_polis,
            'NOMOR REGISTER': no_reg,
            'THE INSURED': insured_name,
            'COB': cob_treaty,
            'UW YEAR': uy_final,
            'INCEPTION': inception,
            'EXPIRY': expiry,
            'DOL': dol_date,
            'CURRENCY': currency,
            'CLAIM AMOUNT': claim_amount,
            'QS': quota_share,
            'SPL': surplus,
            'calculated_rumus': calculated_rumus,
            'fallback_rumus': fallback_rumus,
            '_orig_idx': np.arange(len(df_claim))
        })

        df_joined = cls._merge_with_treaty(df_clean, df_treaty)

        qs_mult = df_joined['share_qs_panel_of_share_reas'].fillna(0.0)
        sp_mult = df_joined['share_sp_panel_of_share_reas'].fillna(0.0)

        df_joined['multiplied_quota_share'] = df_joined['QS'] * qs_mult
        df_joined['multiplied_surplus'] = df_joined['SPL'] * sp_mult

        output_cols = [
            'POLICY NUMBER', 'NOMOR REGISTER', 'THE INSURED', 'COB', 'UW YEAR', 'INCEPTION', 
            'EXPIRY', 'DOL', 'CURRENCY', 'CLAIM AMOUNT', 
            'QS', 'SPL', 'broker_used', 'security_used', 
            'share_qs_panel_of_share_reas', 'share_sp_panel_of_share_reas', 
            'multiplied_quota_share', 'multiplied_surplus'
        ]

        return df_joined[output_cols].copy()

    # KLAIM ALLOCATION
    @classmethod
    def process_asum_allocation_claim(cls, main_file, reference_file) -> pd.DataFrame:
        df_claim = cls._read_file(main_file, required_terms=cls.REQUIRED_KLAIM_GROUPS)
        df_treaty = cls._read_file(reference_file)

        # FIXED: Explicitly grab POLICY_NO and POLICYREF_NO separately
        policy_no = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['POLICY_NO']).astype(str).str.strip()
        policy_refno = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['POLICYREF_NO']).astype(str).str.strip()
        
        # Fallback policy_refno to policy_no if policy_refno is empty/missing
        policy_refno = np.where((policy_refno == '') | (policy_refno == 'nan'), policy_no, policy_refno)
        insured_name = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['INSURED_NAME']).astype(str).str.strip()
        cob_treaty = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['COB_TREATY']).astype(str).str.strip()
        inception = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['INCEPTION']).astype(str).str.strip()
        expiry = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['EXPIRY']).astype(str).str.strip()
        dol_date = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['DOL_DATE']).astype(str).str.strip()
        currency = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['CURRENCY']).astype(str).str.strip()
        uy_final = cls._get_column_value(df_claim, cls.COLUMN_MAPPING_KLAIM['UY_FINAL']).astype(str).str.strip()
        
        claim_amount = cls._get_numeric_column(df_claim, cls.COLUMN_MAPPING_KLAIM['CLAIM_AMOUNT'])
        quota_share = cls._get_numeric_column(df_claim, cls.COLUMN_MAPPING_KLAIM['QUOTA_SHARE'])
        surplus = cls._get_numeric_column(df_claim, cls.COLUMN_MAPPING_KLAIM['SURPLUS'])

        calculated_rumus, fallback_rumus = cls._extract_or_build_primary_key(df_claim)

        df_clean = pd.DataFrame({
            'POLICY NUMBER': policy_no,
            'POLICYREF NUMBER': policy_refno,
            'THE INSURED': insured_name,
            'COB': cob_treaty,
            'UW YEAR': uy_final,
            'INCEPTION': inception,
            'EXPIRY': expiry,
            'DOL': dol_date,
            'CURRENCY': currency,
            'CLAIM AMOUNT': claim_amount,
            'QS': quota_share,
            'SPL': surplus,
            'calculated_rumus': calculated_rumus,
            'fallback_rumus': fallback_rumus,
            '_orig_idx': np.arange(len(df_claim))
        })

        df_joined = cls._merge_with_treaty(df_clean, df_treaty)

        qs_mult = df_joined['share_qs_panel_of_share_reas'].fillna(0.0)
        sp_mult = df_joined['share_sp_panel_of_share_reas'].fillna(0.0)

        df_joined['multiplied_quota_share'] = df_joined['QS'] * qs_mult
        df_joined['multiplied_surplus'] = df_joined['SPL'] * sp_mult

        df_joined['qs share per panel'] = df_joined['share_qs_panel_of_share_reas']
        df_joined['sp share per panel'] = df_joined['share_sp_panel_of_share_reas']

        output_cols = [
            'POLICY NUMBER', 'POLICYREF NUMBER', 'THE INSURED', 'COB', 'UW YEAR', 
            'INCEPTION', 'EXPIRY', 'DOL', 'CURRENCY', 'CLAIM AMOUNT', 
            'QS', 'SPL', 'broker_used', 'security_used', 
            'qs share per panel', 'sp share per panel',
            'share_qs_panel_of_share_reas', 'share_sp_panel_of_share_reas', 
            'multiplied_quota_share', 'multiplied_surplus'
        ]

        return df_joined[output_cols].copy()