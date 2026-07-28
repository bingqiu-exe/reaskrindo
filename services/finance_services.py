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

    @classmethod
    def _get_column_value(cls, df: pd.DataFrame, possible_names: list, default=None):
        for col in possible_names:
            for actual_col in df.columns:
                if actual_col.strip().lower() == col.lower():
                    return df[actual_col]
        return pd.Series(default, index=df.index)

    @classmethod
    def _normalize_key_string(cls, series: pd.Series) -> pd.Series:
        return (
            series.astype(str)
            .str.upper()
            .str.replace(r'[\s\-_/]+', '', regex=True)
            .str.strip()
        )

    @classmethod
    def _extract_or_build_primary_key(cls, df: pd.DataFrame, is_reference: bool = False) -> tuple[pd.Series, pd.Series]:
        possible_pk_cols = [
            'rumus', 'rumus_key', 'pk', 'primary_key'
        ]
        
        existing_pk_col = None
        for col in df.columns:
            cleaned_col_name = col.strip().lower().replace(' ', '')
            if cleaned_col_name in [p.replace('-', '').replace('_', '').replace('/', '') for p in possible_pk_cols]:
                existing_pk_col = col
                break

        if existing_pk_col is not None:
            raw_key = df[existing_pk_col].astype(str)
            calculated_key = cls._normalize_key_string(raw_key)
            fallback_key = calculated_key
            return calculated_key, fallback_key

        cob_series = cls._get_column_value(df, ['cob_treaty', 'cob', 'class_of_business']).astype(str).str.strip()
        uy_series = cls._get_column_value(df, ['uy_final', 'uy', 'underwriting_year']).astype(str).str.strip()

        calculated_key = cls._normalize_key_string(uy_series + cob_series)

        uy_4digits = uy_series.str.slice(0, 4)
        fallback_key = cls._normalize_key_string(uy_4digits + cob_series)

        return calculated_key, fallback_key

    @classmethod
    def process_asum_allocation(cls, main_file, reference_file) -> pd.DataFrame:
        df_claim = cls._read_file(main_file)
        df_treaty = cls._read_file(reference_file)

        def clean_numeric(series):
            s = series.astype(str).str.strip().replace({'': '0', 'nan': '0', 'None': '0'})
            s = s.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            return pd.to_numeric(s, errors='coerce').fillna(0.0)

        claim_amt = clean_numeric(cls._get_column_value(df_claim, ['CLAIM_AMOUNT', 'claim_amount', 'gross', 'gros']))
        qs_amt = clean_numeric(cls._get_column_value(df_claim, ['QUOTA_SHARE', 'quota_share', 'qs', 'reas_qs']))
        sp_amt = clean_numeric(cls._get_column_value(df_claim, ['SURPLUS', 'surplus', 'sp', 'spl', 'reas_sp']))

        policy_no = cls._get_column_value(df_claim, ['POLICY_NO', 'no_sertifikat', 'no_polis']).astype(str).str.strip()
        policy_refno = cls._get_column_value(df_claim, ['POLICY_REFNO', 'no_klaim', 'claim_no']).astype(str).str.strip()
        insured_name = cls._get_column_value(df_claim, ['INSURED_NAME', 'nama_debitur', 'nm_debitur']).astype(str).str.strip()
        cob_treaty = cls._get_column_value(df_claim, ['COB_treaty', 'cob']).astype(str).str.strip()
        uy_final = cls._get_column_value(df_claim, ['uy_final', 'uy']).astype(str).str.strip()

        clean_insured = (
            insured_name.str.replace(';', ' and ', regex=False)
            .str.replace('`', '', regex=False)
            .str.replace("'", '', regex=False)
            .str.replace(r'[\r\n\t]+', ' ', regex=True)
            .str.slice(0, 120)
        )

        calculated_rumus, fallback_rumus = cls._extract_or_build_primary_key(df_claim, is_reference=False)

        df_claim_clean = pd.DataFrame({
            'POLICY_NO': policy_no,
            'POLICY_REFNO': policy_refno,
            'INSURED_NAME': clean_insured,
            'COB_treaty': cob_treaty,
            'INCEPTION': cls._get_column_value(df_claim, ['INCEPTION', 'tgl_awal', 'tanggal_awal']),
            'EXPIRY': cls._get_column_value(df_claim, ['EXPIRY', 'tgl_akhir', 'tanggal_akhir']),
            'DOL_DATE': cls._get_column_value(df_claim, ['DOL_DATE', 'tanggal_agenda', 'tgl_agenda']),
            'CURRENCY': cls._get_column_value(df_claim, ['CURRENCY', 'valuta']),
            'uy_final': uy_final,
            'CLAIM_AMOUNT': claim_amt,
            'QUOTA_SHARE': qs_amt,
            'SURPLUS': sp_amt,
            'calculated_rumus': calculated_rumus,
            'fallback_rumus': fallback_rumus,
            '_orig_idx': np.arange(len(df_claim))
        })

        treaty_rumus, _ = cls._extract_or_build_primary_key(df_treaty, is_reference=True)

        broker_raw = cls._get_column_value(df_treaty, ['broker_used', 'broker']).astype(str)
        security_raw = cls._get_column_value(df_treaty, ['security_used', 'security']).astype(str)
        share_qs_panel = pd.to_numeric(cls._get_column_value(df_treaty, ['share_qs_panel_of_share_reas', 'share_qs']), errors='coerce').fillna(0.0)
        share_sp_panel = pd.to_numeric(cls._get_column_value(df_treaty, ['share_sp_panel_of_share_reas', 'share_sp']), errors='coerce').fillna(0.0)

        kw_pattern = '|'.join(cls.SECURITY_KEYWORDS)
        split_regex = rf',\s*(?=(?:{kw_pattern})\b)'

        expanded_rows = []
        for idx in range(len(df_treaty)):
            r_key = treaty_rumus.iloc[idx]
            b_list = [b.strip() for b in re.split(split_regex, broker_raw.iloc[idx], flags=re.IGNORECASE) if b.strip()]
            s_list = [s.strip() for s in re.split(split_regex, security_raw.iloc[idx], flags=re.IGNORECASE) if s.strip()]

            max_len = max(len(b_list), len(s_list), 1)
            for i in range(max_len):
                b_val = b_list[i] if i < len(b_list) else (b_list[0] if b_list else '')
                s_val = s_list[i] if i < len(s_list) else (s_list[0] if s_list else '')
                expanded_rows.append({
                    'rumus_key': r_key,
                    'broker_used': b_val,
                    'security_used': s_val,
                    'share_qs_panel_of_share_reas': share_qs_panel.iloc[idx],
                    'share_sp_panel_of_share_reas': share_sp_panel.iloc[idx]
                })

        df_expanded = pd.DataFrame(expanded_rows)

        df_cleaned_treaty = df_expanded.groupby(['rumus_key', 'broker_used', 'security_used'], as_index=False).agg({
            'share_qs_panel_of_share_reas': 'max',
            'share_sp_panel_of_share_reas': 'max'
        })

        known_rumus_keys = set(df_cleaned_treaty['rumus_key'].unique())

        merged_primary = pd.merge(
            df_claim_clean,
            df_cleaned_treaty,
            left_on='calculated_rumus',
            right_on='rumus_key',
            how='inner'
        )

        unmatched_claims = df_claim_clean[~df_claim_clean['calculated_rumus'].isin(known_rumus_keys)]
        merged_fallback = pd.merge(
            unmatched_claims,
            df_cleaned_treaty,
            left_on='fallback_rumus',
            right_on='rumus_key',
            how='inner'
        )

        matched_orig_indices = set(merged_primary['_orig_idx']).union(set(merged_fallback['_orig_idx']))
        unmatched_all = df_claim_clean[~df_claim_clean['_orig_idx'].isin(matched_orig_indices)].copy()

        unmatched_all['rumus_key'] = np.nan
        unmatched_all['broker_used'] = np.nan
        unmatched_all['security_used'] = np.nan
        unmatched_all['share_qs_panel_of_share_reas'] = np.nan
        unmatched_all['share_sp_panel_of_share_reas'] = np.nan

        df_joined = pd.concat([merged_primary, merged_fallback, unmatched_all], ignore_index=True)
        df_joined = df_joined.sort_values(by=['_orig_idx', 'security_used'], na_position='last').reset_index(drop=True)

        df_joined['_partition_rank'] = df_joined.groupby(['POLICY_REFNO', 'POLICY_NO']).cumcount() + 1
        df_joined['QUOTA_SHARE'] = np.where(df_joined['_partition_rank'] == 1, df_joined['QUOTA_SHARE'], 0.0)

        qs_multiplier = np.where(df_joined['share_qs_panel_of_share_reas'].notna(), df_joined['share_qs_panel_of_share_reas'], np.where(df_joined['rumus_key'].isna(), 1.0, 0.0))
        sp_multiplier = np.where(df_joined['share_sp_panel_of_share_reas'].notna(), df_joined['share_sp_panel_of_share_reas'], np.where(df_joined['rumus_key'].isna(), 1.0, 0.0))

        df_joined['multiplied_quota_share'] = df_joined['QUOTA_SHARE'] * qs_multiplier
        df_joined['multiplied_surplus'] = df_joined['SURPLUS'] * sp_multiplier

        output_cols = [
            'POLICY_NO', 'POLICY_REFNO', 'INSURED_NAME', 'COB_treaty', 'INCEPTION', 
            'EXPIRY', 'DOL_DATE', 'CURRENCY', 'uy_final', 'CLAIM_AMOUNT', 
            'QUOTA_SHARE', 'SURPLUS', 'broker_used', 'security_used', 
            'share_qs_panel_of_share_reas', 'share_sp_panel_of_share_reas', 
            'multiplied_quota_share', 'multiplied_surplus'
        ]

        return df_joined[output_cols].copy()

    @staticmethod
    def _read_file(uploaded_file) -> pd.DataFrame:
        filename = uploaded_file.name.lower()
        if filename.endswith('.csv'):
            return pd.read_csv(uploaded_file)
        elif filename.endswith(('.xls', '.xlsx')):
            return pd.read_excel(uploaded_file)
        else:
            raise ValidationError("Unsupported file format. Please upload CSV or Excel (.xlsx).")

    @classmethod
    def export_to_excel(cls, df: pd.DataFrame) -> bytes:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Allocation Result')
        return output.getvalue()