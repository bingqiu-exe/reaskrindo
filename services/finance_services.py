import re
import io
import numpy as np
import pandas as pd
from django.core.exceptions import ValidationError

class FinanceServices:
    
    SECURITY_KEYWORDS = [
        "ASURANSI", "REASURANSI", "PT", "MUNICH", "PARTNER", "BRINGIN", "TUGU", 
        "PLN", "ASIA", "MEGARE", "TRINITY", "ARTHARE", "APLN", "ARB", "ASKRINDO", 
        "ODYSSEY", "BEST", "ASPEN", "SAUDI", "GENERAL", "CANOPIUS", "CHINA", 
        "VOLANTE", "QBE", "TOKIO", "CHAUCER", "PVI", "HANNOVER"
    ]

    REQUIRED_PREMI_KEYWORDS = ['sertifikat', 'debitur', 'cob', 'inception', 'expiry', 'currency', 'uy', 'tsi']
    REQUIRED_KLAIM_KEYWORDS = ['sertifikat', 'debitur', 'cob', 'inception', 'expiry', 'currency', 'uy', 'gros']

    @classmethod
    def _read_file(cls, uploaded_file, required_terms: list = None) -> pd.DataFrame:
        filename = uploaded_file.name.lower()
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        
        if filename.endswith('.csv'):
            read_fn = lambda header_row: pd.read_csv(io.BytesIO(file_bytes), header=header_row)
        elif filename.endswith(('.xls', '.xlsx')):
            read_fn = lambda header_row: pd.read_excel(io.BytesIO(file_bytes), header=header_row)
        else:
            raise ValidationError("Unsupported file format. Please upload CSV or Excel (.xlsx).")

        if not required_terms:
            return read_fn(0)

        for header_idx in range(5):
            try:
                df = read_fn(header_idx)
                cols_str = " ".join([str(c).lower() for c in df.columns])
                if all(term.lower() in cols_str for term in required_terms):
                    return df
            except Exception:
                continue

        raise ValidationError(
            f"Failed to detect required header columns in the first 5 rows of '{uploaded_file.name}'. "
            f"Required terms: {', '.join(required_terms)}"
        )

    @classmethod
    def _get_column_value(cls, df: pd.DataFrame, possible_names: list, default="") -> pd.Series:
        for col in possible_names:
            for actual_col in df.columns:
                if str(actual_col).strip().lower() == col.lower():
                    return df[actual_col]
        return pd.Series(default, index=df.index)

    @classmethod
    def _get_numeric_column(cls, df: pd.DataFrame, possible_names: list, default=0.0) -> pd.Series:
        s = cls._get_column_value(df, possible_names, default=default)
        s_clean = s.astype(str).str.strip().replace({'': '0', 'nan': '0', 'None': '0'})
        s_clean = s_clean.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        return pd.to_numeric(s_clean, errors='coerce').fillna(default)

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
        possible_pk_cols = ['rumus', 'rumus_key', 'pk', 'primary_key']
        
        existing_pk_col = None
        for col in df.columns:
            cleaned_col_name = str(col).strip().lower().replace(' ', '')
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

        cob_series = cls._get_column_value(df, ['cob_treaty', 'cob', 'class_of_business']).astype(str).str.strip()
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
        share_qs_panel = cls._get_numeric_column(df_treaty, ['share_qs_panel_of_share_reas', 'share_qs'])
        share_sp_panel = cls._get_numeric_column(df_treaty, ['share_sp_panel_of_share_reas', 'share_sp'])

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
        unmatched_all['komisi_qs_per_panel'] = 0.0
        unmatched_all['komisi_sp_per_panel'] = 0.0
        unmatched_all['share_qs_panel_of_share_reas'] = 0.0
        unmatched_all['share_sp_panel_of_share_reas'] = 0.0

        df_joined = pd.concat([merged_primary, merged_fallback, unmatched_all], ignore_index=True)
        df_joined = df_joined.sort_values(by=['_orig_idx', 'security_used'], na_position='last').reset_index(drop=True)

        return df_joined

    # FINANCE PREMI
    @classmethod
    def process_finance_allocation_premi(cls, main_file, reference_file) -> pd.DataFrame:
        df_premi = cls._read_file(main_file, required_terms=cls.REQUIRED_PREMI_KEYWORDS)
        df_treaty = cls._read_file(reference_file)

        no_sertifikat = cls._get_column_value(df_premi, [
            'no. sertifikat', 'no_sertifikat', 'certificateno', 
            'certificate_no', 'certificate no', 'certificate no.', 
            'certificate num', 'certificate_num'
        ]).astype(str).str.strip()
        
        nama_debitur = cls._get_column_value(df_premi, [
            'nama debitur', 'nama_debitur', 'debitur', 
            'insured_name', 'insured name', 'insured'
        ]).astype(str).str.strip()
        
        cob_treaty = cls._get_column_value(df_premi, ['cob_treaty', 'cob', 'cob treaty']).astype(str).str.strip()
        inception = cls._get_column_value(df_premi, ['inception', 'tgl_awal', 'tanggal_awal', 'start_date', 'period of ins. awal']).astype(str).str.strip()
        expiry = cls._get_column_value(df_premi, ['expiry', 'tgl_akhir', 'tanggal_akhir', 'end_date', 'period of ins. akhir']).astype(str).str.strip()
        dol_date = cls._get_column_value(df_premi, ['dol_date', 'dol', 'tgl_agenda', 'tanggal_agenda']).astype(str).str.strip()
        currency = cls._get_column_value(df_premi, ['currency', 'curr', 'valuta']).astype(str).str.strip()
        uy_final = cls._get_column_value(df_premi, ['uy_final', 'uy', 'uw_year', 'uw year']).astype(str).str.strip()
        
        tsi_share = cls._get_numeric_column(df_premi, ['tsi_share', 'tsi', 'tsi share'])
        quota_share = cls._get_numeric_column(df_premi, ['quota_share', 'qs', 'reas_qs'])
        surplus = cls._get_numeric_column(df_premi, ['surplus', 'sp', 'reas_sp', 'spl'])

        calculated_rumus, fallback_rumus = cls._extract_or_build_primary_key(df_premi)

        df_clean = pd.DataFrame({
            'No. Sertifikat': no_sertifikat,
            'Nama Debitur': nama_debitur,
            'COB': cob_treaty,
            'Tanggal Awal': inception,
            'Tanggal Akhir': expiry,
            'Tanggal Agenda': dol_date,
            'CURRENCY': currency,
            'uy_final': uy_final,
            'TSI_SHARE': tsi_share,
            'QUOTA_SHARE': quota_share,
            'SURPLUS': surplus,
            'calculated_rumus': calculated_rumus,
            'fallback_rumus': fallback_rumus,
            '_orig_idx': np.arange(len(df_premi))
        })

        df_joined = cls._merge_with_treaty(df_clean, df_treaty)

        qs_mult = df_joined['share_qs_panel_of_share_reas'].fillna(0.0)
        sp_mult = df_joined['share_sp_panel_of_share_reas'].fillna(0.0)

        df_joined['multiplied_quota_share'] = df_joined['QUOTA_SHARE'] * qs_mult
        df_joined['multiplied_surplus'] = df_joined['SURPLUS'] * sp_mult

        df_joined['komisi_qs'] = df_joined['komisi_qs_per_panel'] * df_joined['multiplied_quota_share']
        df_joined['komisi_sp'] = df_joined['komisi_sp_per_panel'] * df_joined['multiplied_surplus']

        output_cols = [
            'NO_SERTIFIKAT', 'NAMA_DEBITUR', 'COB_treaty', 'INCEPTION', 
            'EXPIRY', 'DOL_DATE', 'CURRENCY', 'uy_final', 'TSI_SHARE', 
            'QUOTA_SHARE', 'SURPLUS', 'broker_used', 'security_used', 'komisi_qs_per_panel', 'komisi_sp_per_panel',
            'share_qs_panel_of_share_reas', 'share_sp_panel_of_share_reas', 
            'multiplied_quota_share', 'multiplied_surplus', 'komisi_qs', 'komisi_sp'
        ]

        return df_joined[output_cols].copy()

    # FINANCE KLAIM
    @classmethod
    def process_finance_allocation_claim(cls, main_file, reference_file) -> pd.DataFrame:
        df_claim = cls._read_file(main_file, required_terms=cls.REQUIRED_KLAIM_KEYWORDS)
        df_treaty = cls._read_file(reference_file)

        no_sertifikat = cls._get_column_value(df_claim, [
            'no. sertifikat', 'no_sertifikat', 'certificateno', 
            'certificate_no', 'certificate no', 'certificate no.', 
            'certificate num', 'certificate_num'
        ]).astype(str).str.strip()
        
        no_reg = cls._get_column_value(df_claim, [
            'no_reg', 'no. reg', 'nomor register', 'nomor_register', 
            'reg_no', 'registration number', 'registration_number', 
            'regis_no', 'no. regis', 'no. register', 'preliminary_no', 
            'preliminary_num', 'no. preliminary', 'preliminaryno'
        ]).astype(str).str.strip()

        nama_debitur = cls._get_column_value(df_claim, [
            'nama debitur', 'nama_debitur', 'debitur', 
            'insured_name', 'insured name', 'insured'
        ]).astype(str).str.strip()
        
        cob_treaty = cls._get_column_value(df_claim, ['cob_treaty', 'cob', 'cob treaty']).astype(str).str.strip()
        inception = cls._get_column_value(df_claim, ['inception', 'tgl_awal', 'tanggal_awal', 'start_date', 'period of ins. awal']).astype(str).str.strip()
        expiry = cls._get_column_value(df_claim, ['expiry', 'tgl_akhir', 'tanggal_akhir', 'end_date', 'period of ins. akhir']).astype(str).str.strip()
        dol_date = cls._get_column_value(df_claim, ['dol_date', 'dol', 'tgl_agenda', 'tanggal_agenda']).astype(str).str.strip()
        currency = cls._get_column_value(df_claim, ['currency', 'curr', 'valuta']).astype(str).str.strip()
        uy_final = cls._get_column_value(df_claim, ['uy_final', 'uy', 'uw_year', 'uw year']).astype(str).str.strip()
        
        gross_amount = cls._get_numeric_column(df_claim, [
            'gros', 'gross', 'gross_amount', 'claim_amount', 'claim amount', 'claimamount'
        ])
        
        quota_share = cls._get_numeric_column(df_claim, ['quota_share', 'qs', 'reas_qs'])
        surplus = cls._get_numeric_column(df_claim, ['surplus', 'sp', 'reas_sp', 'spl'])

        calculated_rumus, fallback_rumus = cls._extract_or_build_primary_key(df_claim)

        df_clean = pd.DataFrame({
            'No. Sertifikat': no_sertifikat,
            'No. Registrasi': no_reg,
            'Nama Debitur': nama_debitur,
            'COB': cob_treaty,
            'Tanggal Awal': inception,
            'Tanggal Akhir': expiry,
            'Tanggal Agenda': dol_date,
            'CURRENCY': currency,
            'UY': uy_final,
            'GROSS': gross_amount,
            'QUOTA SHARE': quota_share,
            'SURPLUS': surplus,
            'calculated_rumus': calculated_rumus,
            'fallback_rumus': fallback_rumus,
            '_orig_idx': np.arange(len(df_claim))
        })

        df_joined = cls._merge_with_treaty(df_clean, df_treaty)

        qs_mult = df_joined['share_qs_panel_of_share_reas'].fillna(0.0)
        sp_mult = df_joined['share_sp_panel_of_share_reas'].fillna(0.0)

        df_joined['multiplied_quota_share'] = df_joined['QUOTA_SHARE'] * qs_mult
        df_joined['multiplied_surplus'] = df_joined['SURPLUS'] * sp_mult

        output_cols = [
            'No. Sertifikat', 'No. Registrasi', 'Nama Debitur', 'COB', 'Tanggal Awal', 
            'Tanggal Akhir', 'Tanggal Agenda', 'CURRENCY', 'UY', 'GROSS', 
            'QUOTA SHARE', 'SURPLUS', 'broker_used', 'security_used', 
            'share_qs_panel_of_share_reas', 'share_sp_panel_of_share_reas', 
            'multiplied_quota_share', 'multiplied_surplus'
        ]

        return df_joined[output_cols].copy()