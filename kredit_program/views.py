import io
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
import json
import pandas as pd

from .models import KreditProgram
from services.kp_services import KPServices

@csrf_exempt
@require_http_methods(["POST"])
def process_and_export_kp(request):
    # 1. Validate required files
    if 'main_file' not in request.FILES or 'reference_file' not in request.FILES:
        return JsonResponse({'error': 'Both "main_file" and "reference_file" must be uploaded.'}, status=400)

    main_file = request.FILES['main_file']
    reference_file = request.FILES['reference_file']

    # 2. Extract parameters (checking POST data first, then GET query params)
    raw_jenis_soa = (
        request.POST.get('jenis_soa') or 
        request.GET.get('jenis_soa') or 
        getattr(KreditProgram.JenisSOA, 'KLAIM', 'KLAIM')
    )
    jenis_soa = str(raw_jenis_soa).strip().upper()

    export_format = request.GET.get('export_format', request.POST.get('export_format', 'excel')).lower()

    try:
        # 3. Route processing based on SOA type
        if jenis_soa == getattr(KreditProgram.JenisSOA, 'PREMI', 'PREMI'):
            result_df = KPServices.process_kp_allocation_premi(main_file, reference_file)
        else:
            result_df = KPServices.process_kp_allocation_claim(main_file, reference_file)

        # 4. Handle potential missing output columns safely (e.g. DOL in Premi)
        for col in result_df.columns:
            if result_df[col].isna().all():
                result_df[col] = ""

        # 5. Log processing record to the database
        KreditProgram.objects.create(
            main_filename=main_file.name,
            reference_filename=reference_file.name,
            total_rows_processed=len(result_df),
            jenis_soa=jenis_soa
        )

        # 6. Format and export output
        filename_prefix = f"kp_spreading_{jenis_soa.lower()}_result"

        if export_format == 'excel':
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                result_df.to_excel(writer, index=False, sheet_name='KREDIT PROGRAM Spreading')
            
            excel_bytes = output.getvalue()

            response = HttpResponse(
                excel_bytes,
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
            json_records = json.loads(result_df.to_json(orient='records', date_format='iso'))
            return JsonResponse({
                'message': 'Data processed successfully.',
                'jenis_soa': jenis_soa,
                'total_rows': len(result_df),
                'results': json_records
            }, status=200)

    except ValidationError as e:
        return JsonResponse({'error': e.message if hasattr(e, 'message') else str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)