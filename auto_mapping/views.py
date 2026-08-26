import io
import os
import json
import pandas as pd
from django.http import FileResponse, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.core.exceptions import ValidationError

from services.auto_mapping_services import AutoMappingServices
from .models import AutoMapping

@csrf_exempt
@require_http_methods(["POST"])
def import_cob_uy(request):
    main_file = request.FILES.get('main_file')
    reference_file = request.FILES.get('reference_file', None)
    
    # Extract query params & post data
    file_format = request.GET.get('format', 'json').lower()
    
    # Parse use_primary_key checkbox value (comes as string 'true'/'false' from FormData)
    use_pk_raw = request.POST.get('use_primary_key', 'true')
    use_primary_key = use_pk_raw.lower() in ['true', '1', 't']

    if not main_file:
        return JsonResponse({"error": "Please provide 'main_file'."}, status=400)

    try:
        # 1. Run core mapping logic
        processed_df = AutoMappingServices.process_auto_mapping(
            main_file=main_file,
            reference_file=reference_file,
            use_primary_key=use_primary_key
        )

        # 2. Record analytics/history entry in DB
        unmapped_count = int(processed_df['cob_treaty'].isna().sum()) if 'cob_treaty' in processed_df.columns else 0
        AutoMapping.objects.create(
            main_file_name=main_file.name,
            reference_file_name=reference_file.name if reference_file else None,
            total_rows=len(processed_df),
            unmapped_cob_count=unmapped_count
        )

        base_filename = os.path.splitext(main_file.name)[0]
        filename_prefix = f"mapped_{base_filename}"

        # 3. Export as Excel file
        if file_format in ['excel', 'xlsx']:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                processed_df.to_excel(writer, index=False)
            buffer.seek(0)
            
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename_prefix}.xlsx"'
            return response
    
        # 4. Export as CSV file
        elif file_format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename_prefix}.csv"'
            processed_df.to_csv(path_or_buf=response, index=False)
            return response
    
        # 5. Default: Output JSON for Interactive Frontend Table Preview
        else:
            PREVIEW_LIMIT = 500
            total_records = len(processed_df)
                
            # Slice top N rows & replace NaN with empty string to avoid JSON null quirks
            preview_df = processed_df.head(PREVIEW_LIMIT).fillna("")
            json_records = json.loads(preview_df.to_json(orient='records', date_format='iso'))
                
            return JsonResponse({
                'message': f'Data processed successfully. Showing top {min(PREVIEW_LIMIT, total_records)} of {total_records} rows.',
                'total_rows': total_records,
                'unmapped_count': unmapped_count,
                'columns': list(processed_df.columns),
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
        filename = "mapping toc ke cob treaty.csv"
        content_type = "text/csv"
    else:
        filename = "mapping toc ke cob treaty.xlsx"
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        
    file_path = os.path.join(settings.BASE_DIR, 'static', 'templates', filename)

    if not os.path.exists(file_path):
        return JsonResponse(
            {"error": f"Template file '{filename}' tidak ditemukan di server backend."}, 
            status=404
        )
    
    try:
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        return JsonResponse({"error": f"Gagal membaca file: {str(e)}"}, status=500)