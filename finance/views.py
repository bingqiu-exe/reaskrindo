import io
import json
import os
import pandas as pd
from django.http import FileResponse, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.conf import settings

from services.finance_services import FinanceServices
from finance.models import Finance


@csrf_exempt
@require_http_methods(["POST"])
def process_and_export_finance(request):
    # 1. Validate required files
    if 'main_file' not in request.FILES or 'reference_file' not in request.FILES:
        return JsonResponse({
            'error': 'Both "main_file" and "reference_file" must be uploaded.'
        }, status=400)

    main_file = request.FILES['main_file']
    reference_file = request.FILES['reference_file']

    # 2. Extract parameters
    raw_jenis_soa = (
        request.POST.get('jenis_soa') or 
        request.GET.get('jenis_soa') or 
        getattr(Finance.JenisSOA, 'KLAIM', 'KLAIM')
    )
    jenis_soa = str(raw_jenis_soa).strip().upper()

    export_format = request.GET.get('export_format', request.POST.get('export_format', 'excel')).lower()

    try:
        # 3. Route processing based on SOA type
        if jenis_soa == getattr(Finance.JenisSOA, 'PREMI', 'PREMI'):
            result_df = FinanceServices.process_finance_allocation_premi(main_file, reference_file)
        else:
            result_df = FinanceServices.process_finance_allocation_claim(main_file, reference_file)

        # 4. Handle potential missing output columns safely
        for col in result_df.columns:
            if result_df[col].isna().all():
                result_df[col] = ""

        # 5. Log processing record to the database
        Finance.objects.create(
            main_filename=main_file.name,
            reference_filename=reference_file.name,
            total_rows_processed=len(result_df),
            jenis_soa=jenis_soa
        )

        # 6. Format and export output
        filename_prefix = f"asum_spreading_{jenis_soa.lower()}_result"

        if export_format == 'excel':
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                result_df.to_excel(writer, index=False)

            buffer.seek(0)

            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename_prefix}.xlsx"'
            return response

        elif export_format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename_prefix}.csv"'
            result_df.to_csv(path_or_buf=response, index=False)
            return response

        else:
            # Limit response size for browser preview to avoid browser memory crash
            PREVIEW_LIMIT = 500
            total_records = len(result_df)
            
            # Slice dataframe for preview
            preview_df = result_df.head(PREVIEW_LIMIT)
            json_records = json.loads(preview_df.to_json(orient='records', date_format='iso'))
            
            return JsonResponse({
                'message': f'Data processed successfully. Showing top {min(PREVIEW_LIMIT, total_records)} of {total_records} rows.',
                'jenis_soa': jenis_soa,
                'total_rows': total_records,
                'results': json_records
            }, status=200)

    except ValidationError as e:
        error_msg = e.message if hasattr(e, 'message') else str(e)
        print("\n--- VALIDATION ERROR DETECTED ---")
        print(error_msg)
        print("---------------------------------\n")
        return JsonResponse({'error': error_msg}, status=400)
    except Exception as e:
        import traceback
        print("\n--- SERVER EXCEPTION ---")
        traceback.print_exc()
        print("------------------------\n")
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def download_reference_file(request):
    file_format = request.GET.get('format', 'xlsx').lower()

    if file_format == 'csv':
        filename = "QRY TRATY DAN MAIN CONTRACT TREATY - used database final 20052026 - SQL.csv"
        content_type = "text/csv"
    else: 
        filename = "QRY TRATY DAN MAIN CONTRACT TREATY - used database final 20052026 - SQL.xlsx"
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    file_path = os.path.join(settings.BASE_DIR, 'static', 'templates', filename)

    if not os.path.exists(file_path):
        return JsonResponse(
            {"error": f"Template file '{filename} tidak ditemukan di server backend."},
            status=404
        )
    
    try:
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Conteny-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        return JsonResponse({"error": f"Gagal membaca file: {str(e)}"}, status=500)