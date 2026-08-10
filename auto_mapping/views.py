import io
import pandas as pd
from django.http import HttpResponse, JsonResponse  # Added JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from services.auto_mapping_services import AutoMappingServices
from .models import AutoMapping

@csrf_exempt
@require_http_methods(["POST"])
def import_cob_uy(request):
    main_file = request.FILES.get('main_file')
    reference_file = request.FILES.get('reference_file', None)
    
    # 1. Use request.GET for standard Django views instead of request.query_params
    file_format = request.GET.get('format', 'xlsx').lower()

    if not main_file:
        # Use JsonResponse instead of DRF Response
        return JsonResponse({"error": "Please provide 'main_file'."}, status=400)

    try:
        processed_df = AutoMappingServices.process_auto_mapping(
            main_file=main_file,
            reference_file=reference_file
        )

        # Log to DB
        unmapped_count = int(processed_df['cob_treaty'].isna().sum())
        AutoMapping.objects.create(
            main_file_name=main_file.name,
            reference_file_name=reference_file.name if reference_file else None,
            total_rows=len(processed_df),
            unmapped_cob_count=unmapped_count
        )

        # 2. Dynamically build stream based on requested format
        output = io.BytesIO()
        base_filename = main_file.name.split('.')[0]

        if file_format == 'csv':
            processed_df.to_csv(output, index=False, encoding='utf-8')
            content_type = 'text/csv'
            filename = f"mapped_{base_filename}.csv"
        else:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                processed_df.to_excel(writer, index=False, sheet_name='Mapped_Data')
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f"mapped_{base_filename}.xlsx"

        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        # Use JsonResponse instead of DRF Response
        return JsonResponse({"error": str(e)}, status=400)